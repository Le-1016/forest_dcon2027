package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Mission struct {
	ID          int64     `json:"id"`
	MissionID   string    `json:"mission_id"`
	MissionType string    `json:"mission_type"`
	TargetLat   *float64  `json:"target_lat"`
	TargetLon   *float64  `json:"target_lon"`
	TargetAlt   *float64  `json:"target_alt"`
	TargetClass *string   `json:"target_class"`
	Priority    *string   `json:"priority"`
	Reason      *string   `json:"reason"`
	Status      string    `json:"status"`
	CreatedAt   time.Time `json:"created_at"`
}

type CreateMissionRequest struct {
	MissionType string   `json:"mission_type"`
	TargetLat   *float64 `json:"target_lat"`
	TargetLon   *float64 `json:"target_lon"`
	TargetAlt   *float64 `json:"target_alt"`
	TargetClass *string  `json:"target_class"`
	Priority    *string  `json:"priority"`
	Reason      *string  `json:"reason"`
}

func main() {
	pool, err := pgxpool.New(
		context.Background(),
		os.Getenv("DATABASE_URL"),
	)
	if err != nil {
		log.Fatal(err)
	}
	defer pool.Close()

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if err := pool.Ping(r.Context()); err != nil {
			http.Error(w, "database unavailable", http.StatusServiceUnavailable)
			return
		}

		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok\n"))
	})

	http.HandleFunc("/missions", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			var req CreateMissionRequest
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
				http.Error(w, "invalid JSON", http.StatusBadRequest)
				return
			}

			if req.MissionType != "PATROL" && req.MissionType != "INSPECT" {
				http.Error(w, "mission_type must be PATROL or INSPECT", http.StatusBadRequest)
				return
			}

			var item Mission
			err := pool.QueryRow(
				r.Context(),
				`WITH next AS (
					SELECT nextval(pg_get_serial_sequence('missions', 'id')) AS id
				)
				INSERT INTO missions (
					id, mission_id, mission_type,
					target_lat, target_lon, target_alt,
					target_class, priority, reason, status
				)
				SELECT
					id,
					'MISSION-' || lpad(id::text, 3, '0'),
					$1, $2, $3, $4, $5,
					COALESCE($6, 'NORMAL'),
					COALESCE($7, 'MANUAL_REQUEST'),
					'REQUESTED'
				FROM next
				RETURNING
					id, mission_id, mission_type,
					target_lat, target_lon, target_alt,
					target_class, priority, reason, status, created_at`,
				req.MissionType,
				req.TargetLat,
				req.TargetLon,
				req.TargetAlt,
				req.TargetClass,
				req.Priority,
				req.Reason,
			).Scan(
				&item.ID,
				&item.MissionID,
				&item.MissionType,
				&item.TargetLat,
				&item.TargetLon,
				&item.TargetAlt,
				&item.TargetClass,
				&item.Priority,
				&item.Reason,
				&item.Status,
				&item.CreatedAt,
			)
			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}

			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusCreated)
			if err := json.NewEncoder(w).Encode(item); err != nil {
				log.Printf("encode response: %v", err)
			}
			return
		}

		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		rows, err := pool.Query(
			r.Context(),
			`SELECT
				id, mission_id, mission_type,
				target_lat, target_lon, target_alt,
				target_class, priority, reason, status, created_at
			FROM missions
			ORDER BY id`,
		)

		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		defer rows.Close()

		missions := make([]Mission, 0)

		for rows.Next() {
			var item Mission

			err := rows.Scan(
				&item.ID,
				&item.MissionID,
				&item.MissionType,
				&item.TargetLat,
				&item.TargetLon,
				&item.TargetAlt,
				&item.TargetClass,
				&item.Priority,
				&item.Reason,
				&item.Status,
				&item.CreatedAt,
			)

			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}

			missions = append(missions, item)
		}

		w.Header().Set("Content-Type", "application/json")

		if err := json.NewEncoder(w).Encode(missions); err != nil {
			log.Printf("encode response: %v", err)
		}
	})

	log.Println("FOREST Go API listening on http://0.0.0.0:8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
