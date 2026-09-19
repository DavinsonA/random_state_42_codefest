"""Trae el indice vectorial si falta. Lo ejecuta `entrypoint.sh` al arrancar.

**Por que Python y no `curl`.** La imagen parte de `python:3.11-slim`, que no
trae `curl` ni `wget`. El `HEALTHCHECK` del `Dockerfile` ya usaba `httpx` por
esa razon; esto hace lo mismo. Instalar `curl` con apt costaria una capa nueva
y, peor, invalidaria la cache de `pip install` en cada build.

**Que descarga.** Lo que diga `DATA_FILES`: una lista de `nombre=url` separados
por espacios. Generica a proposito, para que cambiar el origen sea editar una
variable en Coolify y no reconstruir la imagen.

Nunca lanza hacia fuera: si algo falla lo dice y devuelve un codigo distinto de
cero, pero el contenedor sigue vivo. Sin indice el sistema responde y lo declara
en `/health`; un arranque abortado deja los tres dominios en 503 durante la
ventana de evaluacion, que es mucho peor.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

#: Por debajo de esto, lo que bajo no es un indice. Cuando Google Drive excede
#: cuota responde 200 con una pagina HTML: sin esta comprobacion el fallo seria
#: silencioso y solo se notaria al preguntarle algo al sistema.
MINIMO_GRANDE = 100 * 1024 * 1024  # 100 MB

#: Se escribe por trozos: 1,3 GB no caben en memoria de un contenedor de 8 GB
#: que ademas carga el encoder.
TROZO = 4 * 1024 * 1024


def descargar(nombre: str, url: str, destino: Path) -> bool:
    salida = destino / nombre
    if salida.exists():
        print(f"[indice] {nombre} ya presente", flush=True)
        return True

    # Nombre provisional: mientras baja, el archivo NO tiene su nombre
    # definitivo, asi que la API nunca abre un indice a medias —un fallo mucho
    # peor que no tener indice—.
    parcial = destino / f"{nombre}.parcial"
    print(f"[indice] descargando {nombre}", flush=True)
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as r:
            r.raise_for_status()
            with parcial.open("wb") as fh:
                for trozo in r.iter_bytes(TROZO):
                    fh.write(trozo)
    except Exception as exc:  # noqa: BLE001 - un fallo aqui no tumba el arranque
        print(f"[indice] FALLO {nombre}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        parcial.unlink(missing_ok=True)
        return False

    tam = parcial.stat().st_size
    if nombre.endswith((".faiss", ".jsonl")) and tam < MINIMO_GRANDE:
        print(
            f"[indice] {nombre} pesa {tam} B: no es el archivo, es un error del origen",
            file=sys.stderr,
            flush=True,
        )
        parcial.unlink(missing_ok=True)
        return False

    parcial.rename(salida)
    print(f"[indice] {nombre} listo ({tam / 1e6:.0f} MB)", flush=True)
    return True


def main() -> int:
    especificacion = os.getenv("DATA_FILES", "").strip()
    if not especificacion:
        print("[indice] sin DATA_FILES: no hay nada que traer", flush=True)
        return 0

    destino = Path(os.getenv("VECTOR_INDEX_PATH", "data/encoder_bge_m3"))
    destino.mkdir(parents=True, exist_ok=True)

    fallos = 0
    for entrada in especificacion.split():
        nombre, _, url = entrada.partition("=")
        if not nombre or not url:
            print(f"[indice] entrada mal formada, se ignora: {entrada[:60]}", file=sys.stderr)
            fallos += 1
            continue
        if not descargar(nombre, url, destino):
            fallos += 1

    if fallos:
        print(f"[indice] {fallos} archivo(s) no se pudieron traer", file=sys.stderr, flush=True)
        return 1
    print(f"[indice] completo en {destino}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
