package main

import (
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
)

// Keep ML persistence/training separate from flight operations and the Go database.
func trainingProxy() http.Handler {
	address := os.Getenv("FOREST_ML_URL")
	if address == "" {
		address = "http://ml:8090"
	}
	target, err := url.Parse(address)
	if err != nil || target.Host == "" || (target.Scheme != "http" && target.Scheme != "https") {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			http.Error(w, "invalid training service configuration", http.StatusServiceUnavailable)
		})
	}
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		_, _ = w.Write([]byte(`{"error":"学習サービスが起動していません。"}`))
	}
	return http.StripPrefix("/ml", proxy)
}
