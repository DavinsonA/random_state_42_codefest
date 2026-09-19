"""Resolucion del `sesion_id` de `POST /chat`.

Dos clientes distintos: el frontend (controla su id y lo manda siempre) y el
evaluador de ADL (probablemente no manda ninguno). Politica, en orden:

1. campo del cuerpo (`sesion_id`, `session_id`, `thread_id`);
2. header `X-Session-Id`;
3. cookie `sesion_id`;
4. si no hay ninguno valido, el servidor genera uno nuevo (uuid4) y lo devuelve
   por header y cookie: un cliente con cookie jar continua la conversacion solo;
   uno sin ella recibe una sesion nueva por request, que es lo seguro para
   preguntas de evaluacion independientes (no se arrastra historial, tokens ni
   un intento de prompt injection de una pregunta a la siguiente).

Un id enviado por el cliente solo se acepta si tiene forma valida: se usa como
`thread_id` de la memoria y no debe ser una cadena arbitraria.
"""

from __future__ import annotations

import re
from uuid import uuid4

from fastapi import Request, Response

SESSION_HEADER = "X-Session-Id"
SESSION_COOKIE = "sesion_id"
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def resolve_session(body_sid: str | None, request: Request) -> tuple[str, bool]:
    """Devuelve `(sesion_id, es_nueva)`."""
    for candidate in (
        body_sid,
        request.headers.get(SESSION_HEADER),
        request.cookies.get(SESSION_COOKIE),
    ):
        if candidate and _SID_RE.match(candidate):
            return candidate, False
    return uuid4().hex, True


def attach_session(response: Response, session_id: str, is_new: bool, ttl_s: int) -> None:
    """Devuelve el id por header siempre, y por cookie cuando el servidor lo genero."""
    response.headers[SESSION_HEADER] = session_id
    if is_new:
        response.set_cookie(
            SESSION_COOKIE, session_id, max_age=ttl_s, httponly=True, samesite="lax"
        )
