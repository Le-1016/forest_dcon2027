package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestTrainingProxyPreservesAuthAndStripsPrefix(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/worker/claim" || r.Header.Get("Authorization") != "Bearer test" || r.Method != "POST" {
			t.Errorf("unexpected proxy request: %s %s", r.Method, r.URL.Path)
		}
		body, _ := io.ReadAll(r.Body)
		if string(body) != `{"worker_id":"pc"}` {
			t.Errorf("body lost: %s", body)
		}
		w.WriteHeader(http.StatusCreated)
	}))
	defer upstream.Close()
	t.Setenv("FOREST_ML_URL", upstream.URL)
	r := httptest.NewRequest("POST", "/ml/worker/claim", strings.NewReader(`{"worker_id":"pc"}`))
	r.Header.Set("Authorization", "Bearer test")
	w := httptest.NewRecorder()
	trainingProxy().ServeHTTP(w, r)
	if w.Code != http.StatusCreated {
		t.Fatalf("status %d", w.Code)
	}
}

func TestTrainingProxyUnavailable(t *testing.T) {
	t.Setenv("FOREST_ML_URL", "not a URL")
	w := httptest.NewRecorder()
	trainingProxy().ServeHTTP(w, httptest.NewRequest("GET", "/ml/state", nil))
	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("status %d", w.Code)
	}
}
