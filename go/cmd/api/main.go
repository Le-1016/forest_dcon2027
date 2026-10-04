package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Mission struct {
	ID          int64    `json:"id"`
	MissionID   string   `json:"mission_id"`
	MissionType string   `json:"mission_type"`
	TargetLat   *float64 `json:"target_lat"`
	TargetLon   *float64 `json:"target_lon"`
	TargetAlt   *float64 `json:"target_alt"`
	TargetClass *string  `json:"target_class"`
	Priority    *string  `json:"priority"`
	Reason      *string  `json:"reason"`
	Status      string   `json:"status"`
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
		rows, err := pool.Query(
			r.Context(),
			`SELECT
				id, mission_id, mission_type,
				target_lat, target_lon, target_alt,
				target_class, priority, reason, status
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
