#!/bin/sh
set -eu

# На чистом клоне compose.env нет. Процесс всё равно должен стартовать:
# если PRODUCT_SECRET короче 32 символов, берём файл тома или пишем новый.
STORE="${PRODUCT_SECRET_FILE:-/data/product_secret}"
export PRODUCT_SECRET_FILE="$STORE"
SECRET="${PRODUCT_SECRET:-}"
if [ "${#SECRET}" -lt 32 ]; then
  if [ -f "$STORE" ]; then
    SECRET=$(cat "$STORE")
  fi
  if [ "${#SECRET}" -lt 32 ]; then
    SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(32), end="")')
    umask 077
    mkdir -p "$(dirname "$STORE")"
    printf '%s' "$SECRET" > "$STORE"
  fi
  export PRODUCT_SECRET="$SECRET"
fi

python -m product.seed
exec uvicorn product.app.main:app --host 0.0.0.0 --port 8000 --workers 1
