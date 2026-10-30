#!/bin/bash
cd "$(dirname "$0")"

# Browser'ı otomatik aç
(sleep 2 && open http://localhost:8000) &

./run.sh
