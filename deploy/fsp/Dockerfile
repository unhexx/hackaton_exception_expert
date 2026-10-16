# Урезанный корень Python 3.12 linux/amd64: интерпретатор и уже
# установленные пакеты. Полный python:3.12-slim сюда не кладём.
# В нём есть perl-base, и при параллельной распаковке двух образов
# containerd пишет «no space left on device» на
# usr/lib/x86_64-linux-gnu/perl-base/XSLoader.pm.
# Docker Hub и PyPI при сборке не вызываются: pip в этом Dockerfile нет.
FROM scratch
ADD deploy/fsp/python-3.12-slim-rootfs.tar.gz /

ENV LANG=C.UTF-8 \
    PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    LD_LIBRARY_PATH=/usr/local/lib:/usr/lib/x86_64-linux-gnu \
    PYTHONPATH=/srv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    FSP_REALM_FILE=/srv/fsp-realm.json \
    OIDC_PUBLIC_ISSUER=http://127.0.0.1:8080/realms/fsp

WORKDIR /srv

COPY product /srv/product
COPY deploy/fsp/entrypoint.sh /srv/entrypoint.sh
COPY deploy/fsp/fsp-realm.json /srv/fsp-realm.json

EXPOSE 8000

ENTRYPOINT ["/srv/entrypoint.sh"]
