package main

import (
	"encoding/json"
	"log"
	"net/http"

	"github.com/jackc/pgx/v5/pgxpool"
)

func handleObservationHistory(pool *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		areaID := r.URL.Query().Get("area_id")
		siteID := r.URL.Query().Get("site_id")

		if areaID == "" || siteID == "" {
			http.Error(w, "area_id and site_id are required", http.StatusBadRequest)
			return
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
			WHERE area_id = $1 AND site_id = $2
			ORDER BY observed_at DESC, id DESC`,
			areaID,
			siteID,
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

		result := ObservationHistory{
			AreaID:       areaID,
			SiteID:       siteID,
			Count:        len(items),
			Observations: items,
		}

		if len(items) >= 1 {
			result.Latest = &items[0]
		}

		if len(items) >= 2 {
			result.Previous = &items[1]
		}

		w.Header().Set("Content-Type", "application/json")

		if err := json.NewEncoder(w).Encode(result); err != nil {
			log.Printf("encode observation history response: %v", err)
		}
	}
}
