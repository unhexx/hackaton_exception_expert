#!/bin/sh
set -eu
python -m product.seed
exec uvicorn product.app.main:app --host 0.0.0.0 --port 8000 --workers 1
