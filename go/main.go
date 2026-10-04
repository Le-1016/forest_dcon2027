package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/jackc/pgx/v5"
)

func main() {
	connection, err := pgx.Connect(
		context.Background(),
		os.Getenv("DATABASE_URL"),
	)
	if err != nil {
		log.Fatal(err)
	}
	defer connection.Close(context.Background())

	var missionID string

	err = connection.QueryRow(
		context.Background(),
		"SELECT mission_id FROM missions ORDER BY id LIMIT 1",
	).Scan(&missionID)

	if err != nil {
		log.Fatal(err)
	}

	fmt.Printf("FOREST Go connected to PostgreSQL: %s\n", missionID)
}
