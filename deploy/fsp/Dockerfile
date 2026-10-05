FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY product /srv/product
COPY deploy/fsp/entrypoint.sh /srv/entrypoint.sh
COPY deploy/fsp/wheels /tmp/wheels

# Колёса в deploy/fsp/wheels необязательны. Если каталог пуст, pip берёт индекс.
# Так сборка жива и без DNS у моста, и на чистой машине с сетью.
RUN set -eu; \
    if ls /tmp/wheels/*.whl >/dev/null 2>&1; then \
      pip install --no-index --find-links /tmp/wheels setuptools wheel \
      && pip install --no-index --find-links /tmp/wheels --no-build-isolation "/srv/product[dev]"; \
    else \
      pip install "/srv/product[dev]"; \
    fi \
    && chmod 0755 /srv/entrypoint.sh \
    && rm -rf /tmp/wheels

EXPOSE 8000

ENTRYPOINT ["/srv/entrypoint.sh"]
