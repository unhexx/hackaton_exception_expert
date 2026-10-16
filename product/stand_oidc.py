"""Локальный issuer реалма fsp. Образ Keycloak стенд не скачивает.

Слой quay.io/keycloak/keycloak при распаковке пишет в
lib/lib/deployment и на части машин заканчивается «no space left on device».
Кабинеты из-за этого не поднимаются. Здесь только тот кусок OIDC, который
читает связь ID: discovery, форма входа, PKCE S256, обмен кода, подпись RS256.
Реалм берётся из fsp-realm.json. Боевой Keycloak заказчика сюда не входит:
его по-прежнему задают четырьмя переменными окружения приложения.

Ключ ниже подписывает только этот стендовый issuer. Это не секрет заказчика.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_N = int(
    "28381254186619336933124420983164079894462111125484691818727400214268335470574630828557805638579980756729230717441110548836616605440216415305335861231339015265036745268955068903538061013095091916681102344017950486783812545947946889088347845103870374848273525527964871720230742658482638425552204990268836713138549566738438712636931378913458940499589008452444056377035910598925178584256282436742208428447583298118348869201601631251833984886311406300287432803351201470150140348610986075149910795886897674644244087677187650195483403848091005163846366678522091000373365383272454006021075162953521830383683634063550685237767"
)
_D = int(
    "7827721135392798338872552473887763036641132332097876725657370990021015575909360201742475484385193740455913603508045740963063055245657137416293061319362625241057291134916113767275008344022465690220322343398331690859526735649817873776895974398813021050245939098230450566535404259020140239270471356662715077106516314376597108039248507950782193838059435164694606377927028618368256270723720395880566634929228666185930262395600429703061653084234781126681175041250211579324672737913502231308487412728665177581198278806218267282245685650965621353774272346322898919040526963049318218963210263570732208762576796861250110352337"
)
_E = 65537
_KID = "fsp-stand-1"
_CODE_TTL_SECONDS = 120
_TOKEN_TTL_SECONDS = 300
_MAX_BODY = 8192

_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


class Realm:
    def __init__(self, client_id: str, redirect_uris: frozenset[str], users: dict[str, tuple[str, str]]) -> None:
        self.client_id = client_id
        self.redirect_uris = redirect_uris
        self.users = users


class Pending:
    def __init__(
        self,
        challenge: str,
        redirect_uri: str,
        client_id: str,
        username: str,
        expires: float,
    ) -> None:
        self.challenge = challenge
        self.redirect_uri = redirect_uri
        self.client_id = client_id
        self.username = username
        self.expires = expires


class Stand:
    def __init__(self, realm: Realm, issuer: str) -> None:
        self.realm = realm
        self.issuer = issuer.rstrip("/")
        self._codes: dict[str, Pending] = {}
        self._lock = threading.Lock()

    def issue_code(self, challenge: str, redirect_uri: str, client_id: str, username: str) -> str:
        code = secrets.token_urlsafe(32)
        pending = Pending(
            challenge,
            redirect_uri,
            client_id,
            username,
            time.time() + _CODE_TTL_SECONDS,
        )
        with self._lock:
            self._purge(time.time())
            self._codes[code] = pending
        return code

    def take_code(self, code: str) -> Pending | None:
        now = time.time()
        with self._lock:
            self._purge(now)
            pending = self._codes.pop(code, None)
        if pending is None or pending.expires < now:
            return None
        return pending

    def _purge(self, now: float) -> None:
        stale = [key for key, item in self._codes.items() if item.expires < now]
        for key in stale:
            del self._codes[key]


def load_realm(path: Path) -> Realm:
    data = json.loads(path.read_text(encoding="utf-8"))
    clients = data.get("clients")
    if not isinstance(clients, list) or not clients:
        raise ValueError("в реалме нет клиента")
    client = clients[0]
    client_id = client.get("clientId")
    redirects = client.get("redirectUris")
    if not isinstance(client_id, str) or client_id == "":
        raise ValueError("у клиента нет clientId")
    if not isinstance(redirects, list) or not all(isinstance(item, str) and item for item in redirects):
        raise ValueError("у клиента нет redirectUris")
    users: dict[str, tuple[str, str]] = {}
    raw_users = data.get("users")
    if not isinstance(raw_users, list):
        raise ValueError("в реалме нет пользователей")
    for user in raw_users:
        name = user.get("username")
        if not isinstance(name, str) or name == "":
            continue
        password = ""
        for cred in user.get("credentials") or []:
            if isinstance(cred, dict) and cred.get("type") == "password" and isinstance(cred.get("value"), str):
                password = cred["value"]
        external = ""
        attributes = user.get("attributes") or {}
        raw_external = attributes.get("fsp_external_id") if isinstance(attributes, dict) else None
        if isinstance(raw_external, list) and raw_external and isinstance(raw_external[0], str):
            external = raw_external[0]
        elif isinstance(raw_external, str):
            external = raw_external
        users[name] = (password, external)
    if not users:
        raise ValueError("в реалме нет пользователей")
    return Realm(client_id, frozenset(redirects), users)


def default_realm_path() -> Path:
    env = os.environ.get("FSP_REALM_FILE", "").strip()
    if env:
        return Path(env)
    candidate = Path(__file__).resolve().parents[1] / "deploy" / "fsp" / "fsp-realm.json"
    if candidate.is_file():
        return candidate
    return Path("/srv/fsp-realm.json")


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_int(value: int) -> str:
    length = max(1, (value.bit_length() + 7) // 8)
    return b64u(value.to_bytes(length, "big"))


def sign_rs256(message: bytes) -> bytes:
    digest = hashlib.sha256(message).digest()
    info = _SHA256_PREFIX + digest
    n_len = (_N.bit_length() + 7) // 8
    padding = n_len - len(info) - 3
    if padding < 8:
        raise RuntimeError("ключ стенда короче подписи")
    em = b"\x00\x01" + (b"\xff" * padding) + b"\x00" + info
    signature = pow(int.from_bytes(em, "big"), _D, _N)
    return signature.to_bytes(n_len, "big")


def id_token(issuer: str, client_id: str, subject: str, external_id: str) -> str:
    now = int(time.time())
    header = b64u(json.dumps({"alg": "RS256", "typ": "JWT", "kid": _KID}, separators=(",", ":")).encode("utf-8"))
    claims: dict[str, object] = {
        "iss": issuer,
        "sub": subject,
        "aud": client_id,
        "azp": client_id,
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
    }
    if external_id:
        claims["fsp_external_id"] = external_id
    payload = b64u(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signing = f"{header}.{payload}".encode("ascii")
    return signing.decode("ascii") + "." + b64u(sign_rs256(signing))


def jwks() -> dict:
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": _KID,
                "n": b64u_int(_N),
                "e": b64u_int(_E),
            }
        ]
    }


def discovery(issuer: str) -> dict:
    base = issuer.rstrip("/")
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/protocol/openid-connect/auth",
        "token_endpoint": f"{base}/protocol/openid-connect/token",
        "jwks_uri": f"{base}/protocol/openid-connect/certs",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "code_challenge_methods_supported": ["S256"],
    }


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _same(left: str, right: str) -> bool:
    if left == "" or len(left) != len(right):
        return False
    return secrets.compare_digest(left, right)


def _one(params: dict[str, list[str]], name: str) -> str:
    values = params.get(name) or []
    if len(values) != 1:
        return ""
    return values[0]


def _auth_fields(params: dict[str, list[str]]) -> dict[str, str] | str:
    client_id = _one(params, "client_id")
    redirect_uri = _one(params, "redirect_uri")
    state = _one(params, "state")
    challenge = _one(params, "code_challenge")
    method = _one(params, "code_challenge_method")
    response_type = _one(params, "response_type")
    if response_type != "code":
        return "Нужен response_type=code."
    if method != "S256":
        return "Нужен PKCE S256."
    if challenge == "" or len(challenge) > 128:
        return "Нет code_challenge."
    if len(state) > 200:
        return "Слишком длинный state."
    return {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
    }


def _check_client(stand: Stand, fields: dict[str, str]) -> str | None:
    if fields["client_id"] != stand.realm.client_id:
        return "Неизвестный клиент."
    if fields["redirect_uri"] not in stand.realm.redirect_uris:
        return "redirect_uri не из реалма."
    return None


def _page(issuer: str, error: str, fields: dict[str, str] | None) -> bytes:
    title = "Локальный реалм fsp"
    if fields is None:
        body = (
            "<p>Это issuer стенда для связи ID участника. "
            "Образ Keycloak не скачивается: при распаковке на диске кончается место.</p>"
            "<p>Демо-пользователь <code>synth</code>, пароль <code>synth</code>. "
            f"Issuer <code>{_esc(issuer)}</code>.</p>"
        )
    else:
        hidden = "".join(
            f'<input type="hidden" name="{_esc(key)}" value="{_esc(value)}">'
            for key, value in fields.items()
        )
        note = f"<p>{_esc(error)}</p>" if error else ""
        body = (
            "<p>Вход в локальный реалм fsp. Учётная запись стенда: synth / synth.</p>"
            f"{note}"
            f'<form method="post"><label>Имя <input name="username" autocomplete="username"></label> '
            f'<label>Пароль <input name="password" type="password" autocomplete="current-password"></label> '
            f"{hidden}<button type=\"submit\">Войти</button></form>"
        )
    html = (
        "<!DOCTYPE html><html lang=\"ru\"><meta charset=\"utf-8\">"
        f"<title>{title}</title><h1>{title}</h1>{body}"
    )
    return html.encode("utf-8")


def _esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class Handler(BaseHTTPRequestHandler):
    stand: Stand
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        path = self.path.split("?", 1)[0]
        sys.stderr.write(f"{self.command} {path}\n")

    def do_GET(self) -> None:
        path, params = self._split()
        issuer = self.stand.issuer
        base = urllib.parse.urlparse(issuer).path.rstrip("/")
        if path in ("/", ""):
            self._send(200, "text/html; charset=utf-8", _page(issuer, "", None))
            return
        if path == f"{base}/.well-known/openid-configuration":
            self._json(200, discovery(issuer))
            return
        if path == f"{base}/protocol/openid-connect/certs":
            self._json(200, jwks())
            return
        if path == f"{base}/protocol/openid-connect/auth":
            self._auth_form(params, "")
            return
        self._send(404, "text/plain; charset=utf-8", "Нет такого адреса.\n".encode("utf-8"))

    def do_POST(self) -> None:
        path, query = self._split()
        base = urllib.parse.urlparse(self.stand.issuer).path.rstrip("/")
        form = self._form()
        if form is None:
            self._send(400, "text/plain; charset=utf-8", "Тело запроса не разобрано.\n".encode("utf-8"))
            return
        merged = {key: list(values) for key, values in query.items()}
        for key, values in form.items():
            merged[key] = values
        if path == f"{base}/protocol/openid-connect/auth":
            self._login(merged)
            return
        if path == f"{base}/protocol/openid-connect/token":
            self._token(merged)
            return
        self._send(404, "text/plain; charset=utf-8", "Нет такого адреса.\n".encode("utf-8"))

    def _auth_form(self, params: dict[str, list[str]], error: str) -> None:
        fields = _auth_fields(params)
        if isinstance(fields, str):
            self._send(400, "text/plain; charset=utf-8", (fields + "\n").encode("utf-8"))
            return
        refused = _check_client(self.stand, fields)
        if refused is not None:
            self._send(400, "text/plain; charset=utf-8", (refused + "\n").encode("utf-8"))
            return
        status = 200 if error == "" else 401
        self._send(status, "text/html; charset=utf-8", _page(self.stand.issuer, error, fields))

    def _login(self, params: dict[str, list[str]]) -> None:
        fields = _auth_fields(params)
        if isinstance(fields, str):
            self._send(400, "text/plain; charset=utf-8", (fields + "\n").encode("utf-8"))
            return
        refused = _check_client(self.stand, fields)
        if refused is not None:
            self._send(400, "text/plain; charset=utf-8", (refused + "\n").encode("utf-8"))
            return
        username = _one(params, "username")
        password = _one(params, "password")
        user = self.stand.realm.users.get(username)
        if user is None or not _same(user[0], password):
            self._auth_form(params, "Имя или пароль не подошли.")
            return
        code = self.stand.issue_code(
            fields["code_challenge"],
            fields["redirect_uri"],
            fields["client_id"],
            username,
        )
        target = fields["redirect_uri"]
        query = {"code": code}
        if fields["state"]:
            query["state"] = fields["state"]
        separator = "&" if "?" in target else "?"
        location = target + separator + urllib.parse.urlencode(query)
        self._redirect(location)

    def _token(self, params: dict[str, list[str]]) -> None:
        grant = _one(params, "grant_type")
        code = _one(params, "code")
        verifier = _one(params, "code_verifier")
        client_id = _one(params, "client_id")
        redirect_uri = _one(params, "redirect_uri")
        if grant != "authorization_code" or code == "" or verifier == "":
            self._json(400, {"error": "invalid_request"})
            return
        pending = self.stand.take_code(code)
        if pending is None or pending.client_id != client_id or pending.redirect_uri != redirect_uri:
            self._json(400, {"error": "invalid_grant"})
            return
        try:
            got = _challenge(verifier)
        except UnicodeEncodeError:
            self._json(400, {"error": "invalid_grant"})
            return
        if not _same(pending.challenge, got):
            self._json(400, {"error": "invalid_grant"})
            return
        user = self.stand.realm.users.get(pending.username)
        if user is None:
            self._json(400, {"error": "invalid_grant"})
            return
        _password, external = user
        token = id_token(self.stand.issuer, client_id, pending.username, external)
        self._json(200, {"id_token": token, "token_type": "Bearer", "expires_in": _TOKEN_TTL_SECONDS})

    def _split(self) -> tuple[str, dict[str, list[str]]]:
        parsed = urllib.parse.urlsplit(self.path)
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
        return parsed.path, params

    def _form(self) -> dict[str, list[str]] | None:
        raw_length = self.headers.get("Content-Length", "")
        if not raw_length.isdigit():
            return None
        length = int(raw_length)
        if length > _MAX_BODY:
            return None
        try:
            body = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError:
            return None
        return urllib.parse.parse_qs(body, keep_blank_values=False)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, "application/json", json.dumps(payload).encode("utf-8"))

    def _redirect(self, location: str) -> None:
        body = b""
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()
        self.wfile.write(body)

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def make_server(host: str, port: int, realm: Realm, issuer: str) -> ThreadingHTTPServer:
    stand = Stand(realm, issuer)
    handler = type("BoundHandler", (Handler,), {"stand": stand})
    return ThreadingHTTPServer((host, port), handler)


def serve(host: str, port: int, realm_path: Path, issuer: str) -> ThreadingHTTPServer:
    server = make_server(host, port, load_realm(realm_path), issuer)
    thread = threading.Thread(target=server.serve_forever, name="fsp-oidc", daemon=True)
    thread.start()
    return server


def main() -> None:
    issuer = os.environ.get("OIDC_PUBLIC_ISSUER", "http://127.0.0.1:8080/realms/fsp").strip()
    realm = load_realm(default_realm_path())
    server = make_server("0.0.0.0", 8080, realm, issuer)
    host = urllib.parse.urlparse(issuer)
    if host.hostname is None or host.path.rstrip("/") == "":
        raise SystemExit("OIDC_PUBLIC_ISSUER должен быть адресом реалма")
    sys.stderr.write(f"issuer {issuer}\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
