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

type Observation struct {
	ID                  int64     `json:"id"`
	ObservationID       string    `json:"observation_id"`
	MissionID           *string   `json:"mission_id"`
	AreaID              *string   `json:"area_id"`
	SiteID              *string   `json:"site_id"`
	DroneID             *string   `json:"drone_id"`
	ParentObservationID *string   `json:"parent_observation_id"`
	ObservedAt          time.Time `json:"observed_at"`
	Lat                 *float64  `json:"lat"`
	Lon                 *float64  `json:"lon"`
	Altitude            *float64  `json:"altitude"`
	CameraAngle         *float64  `json:"camera_angle"`
	ImagePath           *string   `json:"image_path"`
	Class               *string   `json:"class"`
	Confidence          *float64  `json:"confidence"`
	AIModel             *string   `json:"ai_model"`
	CreatedAt           time.Time `json:"created_at"`
}

type ObservationHistory struct {
	AreaID       string        `json:"area_id"`
	SiteID       string        `json:"site_id"`
	Count        int           `json:"count"`
	Latest       *Observation  `json:"latest"`
	Previous     *Observation  `json:"previous"`
	Observations []Observation `json:"observations"`
}

type CreateObservationRequest struct {
	MissionID           *string  `json:"mission_id"`
	AreaID              *string  `json:"area_id"`
	SiteID              *string  `json:"site_id"`
	DroneID             *string  `json:"drone_id"`
	ParentObservationID *string  `json:"parent_observation_id"`
	Lat                 *float64 `json:"lat"`
	Lon                 *float64 `json:"lon"`
	Altitude            *float64 `json:"altitude"`
	CameraAngle         *float64 `json:"camera_angle"`
	ImagePath           *string  `json:"image_path"`
	Class               *string  `json:"class"`
	Confidence          *float64 `json:"confidence"`
	AIModel             *string  `json:"ai_model"`
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

func handleObservations(pool *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			var req CreateObservationRequest
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
				http.Error(w, "invalid JSON", http.StatusBadRequest)
				return
			}

			if req.Confidence != nil && (*req.Confidence < 0 || *req.Confidence > 1) {
				http.Error(w, "confidence must be between 0 and 1", http.StatusBadRequest)
				return
			}

			var item Observation
			err := pool.QueryRow(
				r.Context(),
				`WITH next AS (
					SELECT nextval(pg_get_serial_sequence('observations', 'id')) AS id
				)
				INSERT INTO observations (
					id, observation_id,
					mission_id, area_id, site_id, drone_id, parent_observation_id,
					lat, lon, altitude, camera_angle,
					image_path, class, confidence, ai_model
				)
				SELECT
					id,
					'OBS-' || lpad(id::text, 4, '0'),
					$1, $2, $3, $4, $5,
					$6, $7, $8, $9,
					$10, $11, $12, $13
				FROM next
				RETURNING
					id, observation_id,
					mission_id, area_id, site_id, drone_id, parent_observation_id,
					observed_at,
					lat, lon, altitude, camera_angle,
					image_path, class, confidence, ai_model, created_at`,
				req.MissionID,
				req.AreaID,
				req.SiteID,
				req.DroneID,
				req.ParentObservationID,
				req.Lat,
				req.Lon,
				req.Altitude,
				req.CameraAngle,
				req.ImagePath,
				req.Class,
				req.Confidence,
				req.AIModel,
			).Scan(
				&item.ID,
				&item.ObservationID,
				&item.MissionID,
				&item.AreaID,
				&item.SiteID,
				&item.DroneID,
				&item.ParentObservationID,
				&item.ObservedAt,
				&item.Lat,
				&item.Lon,
				&item.Altitude,
				&item.CameraAngle,
				&item.ImagePath,
				&item.Class,
				&item.Confidence,
				&item.AIModel,
				&item.CreatedAt,
			)
			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}

			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusCreated)
			if err := json.NewEncoder(w).Encode(item); err != nil {
				log.Printf("encode observation response: %v", err)
			}
			return
		}

		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET, POST")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		areaID := r.URL.Query().Get("area_id")
		siteID := r.URL.Query().Get("site_id")

		var areaFilter, siteFilter *string
		if areaID != "" {
			areaFilter = &areaID
		}
		if siteID != "" {
			siteFilter = &siteID
		}

		rows, err := pool.Query(
			r.Context(),
			`SELECT
				id, observation_id,
				mission_id, area_id, site_id, drone_id, parent_observation_id,
				observed_at,
				lat, lon, altitude, camera_angle,
				image_path, class, confidence, ai_model, created_at
			FROM observations
			WHERE ($1::text IS NULL OR area_id = $1)
			  AND ($2::text IS NULL OR site_id = $2)
			ORDER BY observed_at DESC, id DESC`,
			areaFilter,
			siteFilter,
		)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		defer rows.Close()

		items := make([]Observation, 0)
		for rows.Next() {
			var item Observation
			if err := rows.Scan(
				&item.ID,
				&item.ObservationID,
				&item.MissionID,
				&item.AreaID,
				&item.SiteID,
				&item.DroneID,
				&item.ParentObservationID,
				&item.ObservedAt,
				&item.Lat,
				&item.Lon,
				&item.Altitude,
				&item.CameraAngle,
				&item.ImagePath,
				&item.Class,
				&item.Confidence,
				&item.AIModel,
				&item.CreatedAt,
			); err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			items = append(items, item)
		}

		if err := rows.Err(); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(items); err != nil {
			log.Printf("encode observations response: %v", err)
		}
	}
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

	http.HandleFunc("/observations", handleObservations(pool))
	http.HandleFunc("/tools/observation-history", handleObservationHistory(pool))

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
