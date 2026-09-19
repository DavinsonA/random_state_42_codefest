"""Enrutamiento de la raiz por `Host` y servido de la interfaz estatica.

`RETO.md` §Entregables define tres dominios distintos apuntando al MISMO
contenedor:

    agent.<equipo>....        -> el endpoint que evalua ADL (`POST /chat`)
    frontagent.<equipo>....   -> el chat (Reto 1)
    dashboard.<equipo>....    -> el tablero (Reto 2)

Como Coolify enruta los tres al mismo servicio, es la aplicacion la que decide
que HTML sirve en `/`: `dashboard.*` recibe el tablero y cualquier otro host
recibe el chat. Asi un solo despliegue cubre los tres entregables y no hay un
segundo contenedor que pueda caerse durante la ventana de evaluacion.

Los archivos viven en `src/ui/static/`, que mantiene OTRA sesion. Este modulo nunca
los escribe; si no existen, degrada a un aviso legible en vez de un 500.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from src.config import get_logger

log = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[1] / "ui" / "static"
DASHBOARD_HOST_PREFIX = "dashboard."

_RAIZ = ("/", "/index.html")


def _pagina(host: str) -> str:
    """Archivo que corresponde a un host. La unica regla de enrutamiento."""
    return "dashboard.html" if host.lower().startswith(DASHBOARD_HOST_PREFIX) else "chat.html"


def _aviso(nombre: str) -> HTMLResponse:
    """Degradacion cuando el HTML aun no esta en la imagen.

    Sin estilos ni colores a proposito: los colores viven en `src/theme/`
    (AGENTS.md §2) y esta pagina no es interfaz, es un mensaje de operacion.
    """
    return HTMLResponse(
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<title>A.R.P.I.A.</title></head><body>"
        "<h1>A.R.P.I.A.</h1>"
        f"<p>La interfaz <code>{nombre}</code> no esta incluida en esta imagen.</p>"
        "<p>La API si esta operativa: <code>POST /chat</code>, "
        "<code>GET /agent-card</code>, <code>GET /health</code>.</p>"
        "</body></html>",
        status_code=200,
    )


def install(app: FastAPI) -> None:
    """Instala el middleware de raiz y monta `static/`. Llamar al final del
    arranque: el montaje debe registrarse DESPUES de las rutas de la API para
    que `/chat` y `/health` sigan ganando la resolucion."""

    @app.middleware("http")
    async def host_routing(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Solo interviene en la raiz. Todo lo demas pasa de largo."""
        if request.method in ("GET", "HEAD") and request.url.path in _RAIZ:
            nombre = _pagina(request.headers.get("host", ""))
            archivo = STATIC_DIR / nombre
            if archivo.is_file():
                return FileResponse(archivo, media_type="text/html")
            return _aviso(nombre)
        response: Response = await call_next(request)
        return response

    if STATIC_DIR.is_dir():
        # Doble montaje a proposito: `/static/app.css` y `/app.css` resuelven
        # igual, para no imponerle una convencion de rutas al frontend.
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
        app.mount("/", StaticFiles(directory=STATIC_DIR), name="raiz")
    else:
        log.warning("static/ no existe: se sirve el aviso de degradacion en /")
