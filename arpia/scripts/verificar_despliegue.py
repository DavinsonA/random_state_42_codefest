"""Lista de verificacion de `DEPLOY.md` §7, automatizada.

Sirve contra el contenedor local y contra los dominios de Coolify sin cambiar
nada: lo unico que cambia es `--url`. Cada comprobacion dice que se esperaba y
que se obtuvo, porque a las 07:50 del sabado "fallo" no es informacion
accionable y "index_loaded=false con el resto en verde" si lo es.

    uv run python scripts/verificar_despliegue.py
    uv run python scripts/verificar_despliegue.py --url https://agent.<equipo>...
    uv run python scripts/verificar_despliegue.py --url https://... --con-chat

`--con-chat` es la unica comprobacion que gasta presupuesto: lanza UNA pregunta
real al gateway (2 llamadas). Las demas son gratis. Va desactivada por defecto
para poder repetir la verificacion las veces que haga falta sin pagarla.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx

TIMEOUT_S = 120.0

OK, FALLO, AVISO = "ok", "FALLO", "aviso"


class Verificador:
    """Acumula resultados. No lanza: una comprobacion rota no detiene las demas."""

    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self.cliente = httpx.Client(follow_redirects=True, timeout=TIMEOUT_S)
        self.filas: list[tuple[str, str, str]] = []

    def anotar(self, nombre: str, estado: str, detalle: str = "") -> None:
        self.filas.append((nombre, estado, detalle))

    def get(self, ruta: str, host: str = "") -> tuple[int, Any]:
        cabeceras = {"Host": host} if host else {}
        try:
            r = self.cliente.get(f"{self.url}{ruta}", headers=cabeceras)
        except Exception as exc:  # noqa: BLE001
            return 0, f"{type(exc).__name__}: {exc}"
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text

    # -- comprobaciones -----------------------------------------------------

    def salud(self) -> dict[str, Any]:
        codigo, cuerpo = self.get("/health")
        if codigo != 200 or not isinstance(cuerpo, dict):
            self.anotar("GET /health", FALLO, f"codigo {codigo}: {str(cuerpo)[:120]}")
            return {}

        modo = cuerpo.get("mode")
        # En stub se puntua CERO en calidad: RETO.md prohibe datos simulados en
        # la version desplegada. Es el fallo mas caro y el mas facil de no ver.
        self.anotar(
            "ARPIA_MODE",
            OK if modo == "live" else FALLO,
            f"mode={modo}" + ("" if modo == "live" else "  <-- en stub se puntua 0 en calidad"),
        )
        for campo, critico in (
            ("index_loaded", True),
            ("encoder_listo", True),
            ("gateway_reachable", True),
            ("agent_card_loaded", True),
        ):
            valor = cuerpo.get(campo)
            self.anotar(campo, OK if valor else (FALLO if critico else AVISO), str(valor))

        # Al reves que los demas: aqui lo sano es False. `ARPIA_DEBUG_TRACE=1`
        # publica el texto de las preguntas y los fragmentos recuperados.
        traza = cuerpo.get("debug_trace")
        self.anotar(
            "debug_trace apagado",
            OK if not traza else FALLO,
            "cerrado" if not traza else "ABIERTO: publica el contenido de los turnos",
        )

        memoria = cuerpo.get("memoria_persistente")
        self.anotar(
            "memoria_persistente",
            OK if memoria else AVISO,
            str(memoria)
            + ("" if memoria else "  (se crea al construir el grafo: normal antes del 1er /chat)"),
        )
        return cuerpo

    def agent_card(self) -> None:
        codigo, cuerpo = self.get("/agent-card")
        if codigo != 200 or not isinstance(cuerpo, dict):
            self.anotar("GET /agent-card", FALLO, f"codigo {codigo}")
            return
        # La card de ADL (§2.3) anida la ficha bajo `agente`; no es el estandar
        # A2A, donde el endpoint va en el primer nivel.
        agente = cuerpo.get("agente") or {}
        endpoint = str(agente.get("endpoint") or cuerpo.get("endpoint") or "")
        subagentes = cuerpo.get("subagentes") or []
        self.anotar(
            "GET /agent-card",
            OK if agente.get("nombre") and subagentes else FALLO,
            f"{agente.get('nombre')}, {len(subagentes)} subagentes",
        )
        self.anotar(
            "endpoint de la card",
            OK if endpoint.startswith("https://agent.") and endpoint.endswith("/chat") else FALLO,
            endpoint or "(sin campo agente.endpoint)",
        )

    def agregacion(self) -> None:
        """`filas` vacias = la tabla se construyo antes de montar el indice."""
        codigo, cuerpo = self.get("/api/aggregate?group_by=fenomeno")
        filas = (cuerpo or {}).get("filas") if isinstance(cuerpo, dict) else None
        if codigo != 200 or not filas:
            self.anotar(
                "GET /api/aggregate",
                FALLO,
                f"codigo {codigo}, filas={len(filas or [])}  <-- reiniciar el contenedor",
            )
            return
        self.anotar("GET /api/aggregate", OK, f"{len(filas)} filas: {filas[:3]}")

    def dominios(self) -> None:
        """El mismo contenedor sirve tres dominios segun la cabecera `Host`."""
        for host, espera in (
            ("frontagent.equipo.codefest2026.augusta.avaldigitallabs.com", "chat"),
            ("dashboard.equipo.codefest2026.augusta.avaldigitallabs.com", "tablero"),
        ):
            codigo, cuerpo = self.get("/", host=host)
            texto = cuerpo if isinstance(cuerpo, str) else json.dumps(cuerpo)
            falta = "no está incluida en esta imagen" in texto or "no esta incluida" in texto
            self.anotar(
                f"Host {host.split('.')[0]}.",
                FALLO if (codigo != 200 or falta) else OK,
                f"codigo {codigo}" + (f", falta {espera}.html" if falta else f", {len(texto)} bytes"),
            )

    def evidencia(self) -> None:
        """Trazabilidad: `RETO.md` exige que todo dato llegue a su `chunk_id`."""
        codigo, cuerpo = self.get("/api/components")
        self.anotar("GET /api/components", OK if codigo == 200 else FALLO, f"codigo {codigo}")
        codigo, cuerpo = self.get("/api/geo")
        self.anotar("GET /api/geo", OK if codigo == 200 else FALLO, f"codigo {codigo}")

    def chat(self) -> None:
        """UNA pregunta real. Lo unico que gasta presupuesto: 2 llamadas."""
        try:
            r = self.cliente.post(
                f"{self.url}/chat",
                json={"texto": "Que reporta el corpus sobre capacidades antisatelite?"},
            )
            cuerpo = r.json()
        except Exception as exc:  # noqa: BLE001
            self.anotar("POST /chat", FALLO, f"{type(exc).__name__}: {exc}")
            return

        meta = cuerpo.get("metadata") or {}
        estado, modo = meta.get("estado"), cuerpo.get("mode")
        contexto = (cuerpo.get("evaluacion") or {}).get("retrieval_context") or []
        citas = cuerpo.get("citations") or []

        self.anotar("POST /chat estado", OK if estado == "ok" else FALLO, str(estado))
        self.anotar("POST /chat mode", OK if modo == "live" else FALLO, str(modo))
        # Faithfulness se calcula CONTRA retrieval_context: vacio con RAG activo
        # pierde el 30% del bloque de calidad.
        self.anotar(
            "retrieval_context",
            OK if contexto else FALLO,
            f"{len(contexto)} fragmentos" + ("" if contexto else "  <-- pierde Faithfulness (30%)"),
        )
        self.anotar("citations", OK if citas else FALLO, f"{len(citas)} citas")
        self.anotar(
            "tokens reportados",
            OK if (meta.get("tokens") or {}).get("total") else AVISO,
            f"total={(meta.get('tokens') or {}).get('total')}, "
            f"interacciones={meta.get('num_interacciones')}",
        )

        # El checkpointer se crea al construir el grafo, asi que antes del
        # primer /chat un False es normal y despues NO lo es: significa que
        # CHECKPOINT_PATH apunta a una ruta de solo lectura y la memoria
        # conversacional se pierde en cada redespliegue.
        _, salud = self.get("/health")
        persistente = (salud or {}).get("memoria_persistente") if isinstance(salud, dict) else None
        self.anotar(
            "memoria_persistente (tras /chat)",
            OK if persistente else FALLO,
            str(persistente)
            + ("" if persistente else "  <-- CHECKPOINT_PATH no es escribible"),
        )

        if citas:
            chunk = citas[0].get("chunk_id", "")
            codigo, _ = self.get(f"/api/evidence/{chunk}")
            self.anotar(
                "GET /api/evidence/<cita real>",
                OK if codigo == 200 else FALLO,
                f"codigo {codigo} para {chunk}",
            )

    # -- informe ------------------------------------------------------------

    def informe(self) -> int:
        ancho = max(len(n) for n, _, _ in self.filas)
        print(f"\n{'=' * 78}\nVERIFICACION DE DESPLIEGUE — {self.url}\n{'=' * 78}")
        for nombre, estado, detalle in self.filas:
            marca = {OK: "  ok  ", FALLO: " FALLO", AVISO: " aviso"}[estado]
            print(f"[{marca}] {nombre.ljust(ancho)}  {detalle}")
        fallos = sum(1 for _, e, _ in self.filas if e == FALLO)
        avisos = sum(1 for _, e, _ in self.filas if e == AVISO)
        print(f"\n{len(self.filas)} comprobaciones · {fallos} fallos · {avisos} avisos")
        if not fallos:
            print("\nListo para la ventana de evaluacion.")
        return 1 if fallos else 0


def diagnosticar(url: str) -> list[str]:
    """Por que no responde. "El servicio no responde" no es accionable a las 07:50.

    Las capas se prueban de abajo arriba —DNS, TCP, TLS, HTTP— y se informa la
    primera que falla, porque es la unica que se puede arreglar ahora.
    """
    import socket
    import ssl
    from urllib.parse import urlparse

    partes = urlparse(url)
    host = partes.hostname or ""
    puerto = partes.port or (443 if partes.scheme == "https" else 80)
    out = [f"\n{url} no responde. Diagnostico por capas:"]

    try:
        ip = socket.gethostbyname(host)
        out.append(f"  DNS   ok      {host} -> {ip}")
    except OSError as exc:
        out.append(f"  DNS   FALLO   {host} no resuelve ({exc})")
        out.append("        -> el registro DNS del dominio no existe todavia.")
        return out

    try:
        with socket.create_connection((host, puerto), timeout=10):
            out.append(f"  TCP   ok      {puerto} abierto")
    except OSError as exc:
        out.append(f"  TCP   FALLO   {puerto} cerrado ({exc})")
        out.append("        -> cortafuegos, o no hay proxy escuchando en el servidor.")
        return out

    if partes.scheme == "https":
        try:
            ctx = ssl.create_default_context()
            with (
                socket.create_connection((host, puerto), timeout=10) as sock,
                ctx.wrap_socket(sock, server_hostname=host),
            ):
                out.append("  TLS   ok      certificado valido para el dominio")
        except ssl.SSLCertVerificationError:
            # El caso mas comun en Coolify: Traefik responde con su certificado
            # por defecto porque Let's Encrypt aun no emitio uno para el dominio.
            out.append("  TLS   FALLO   el certificado no cubre este dominio")
            out.append("        -> Traefik responde con TRAEFIK DEFAULT CERT: el dominio no")
            out.append("           esta emitido. Revisar que este escrito en el recurso de")
            out.append("           Coolify (Domains) y que el recurso este desplegado.")
        except OSError as exc:
            out.append(f"  TLS   FALLO   {exc}")

    try:
        r = httpx.get(f"{url.rstrip('/')}/health", timeout=20.0, verify=False)  # noqa: S501
        cuerpo = r.text[:120].strip()
        out.append(f"  HTTP  codigo {r.status_code}   {cuerpo}")
        if r.status_code == 503:
            out.append("        -> 'no available server': el proxy conoce el dominio pero no")
            out.append("           hay contenedor sano detras. Revisar en Coolify el estado")
            out.append("           del recurso y los logs del ultimo despliegue.")
        elif r.status_code == 404:
            out.append("        -> el proxy no tiene ninguna ruta para este dominio: falta")
            out.append("           anadirlo en Domains, con Port 8000 y No redirect.")
    except Exception as exc:  # noqa: BLE001
        out.append(f"  HTTP  FALLO   {type(exc).__name__}: {exc}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument(
        "--con-chat",
        action="store_true",
        help="lanza UNA pregunta real al gateway (2 llamadas). Lo demas es gratis.",
    )
    args = p.parse_args()

    v = Verificador(args.url)
    if not v.salud():
        for linea in diagnosticar(args.url):
            print(linea, file=sys.stderr)
        return 2
    v.agent_card()
    v.agregacion()
    v.dominios()
    v.evidencia()
    if args.con_chat:
        v.chat()
    else:
        print("(POST /chat omitido: anadir --con-chat para probarlo, cuesta 2 llamadas)")
    return v.informe()


if __name__ == "__main__":
    raise SystemExit(main())
