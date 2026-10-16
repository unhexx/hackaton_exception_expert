# Корень python:3.12-slim linux/amd64, sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf.
# Docker Hub при сборке не вызываем: часть его адресов не отвечает
# (dial tcp 52.72.129.195:443: i/o timeout), и метаданные образа не находятся.
FROM scratch
ADD deploy/fsp/python-3.12-slim-rootfs.tar.gz /

ENV LANG=C.UTF-8 \
    PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY product /srv/product
COPY deploy/fsp/entrypoint.sh /srv/entrypoint.sh
COPY deploy/fsp/wheels /tmp/wheels

# Колёса лежат в репозитории, чтобы pip не ходил на PyPI при блокировке индекса.
# Если каталог пуст, остаётся запасной путь через индекс.
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
