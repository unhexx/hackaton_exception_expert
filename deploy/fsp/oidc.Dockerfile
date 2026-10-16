# Тот же корень, что у приложения: Docker Hub при сборке не вызываем.
FROM scratch
ADD deploy/fsp/python-3.12-slim-rootfs.tar.gz /

ENV LANG=C.UTF-8 \
    PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FSP_REALM_FILE=/srv/fsp-realm.json \
    OIDC_PUBLIC_ISSUER=http://127.0.0.1:8080/realms/fsp

COPY product/stand_oidc.py /srv/stand_oidc.py
COPY deploy/fsp/fsp-realm.json /srv/fsp-realm.json

EXPOSE 8080
USER nobody
CMD ["python", "-u", "/srv/stand_oidc.py"]
