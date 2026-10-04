#!/usr/bin/env bash
set -euo pipefail

go mod download

echo "FOREST development environment is ready."
echo "Run 'make check' to test every database connection."
