.PHONY: check check-python check-go jupyter api

check: check-python check-go

check-python:
	python python/check_db.py

check-go:
	go run ./go

jupyter:
	jupyter lab --ip=0.0.0.0 --port=8888 --no-browser

api:
	go run ./go/cmd/api
