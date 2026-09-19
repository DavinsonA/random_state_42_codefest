"""Dimensiones DERIVADAS de la metadata del corpus.

El indice trae ocho campos y ninguno es fecha, lugar ni actor. Dos dimensiones
mas si se pueden obtener sin inventar nada, leyendo la ruta del archivo fuente:

    organizacion -> segundo nivel de la ruta
                    "F1_IA_y_.../Atlantic_Council/..." -> "Atlantic_Council"
    anio         -> ano de cuatro cifras en la ruta o el nombre de archivo

`RETO.md` prohibe presentar como medicion objetiva cualquier puntaje calculado
ad-hoc. Estas dos NO son puntajes: son atributos leidos del propio corpus, y
por eso son licitas. La honestidad exigida es otra: el ano solo se identifica
en 622 de los 1.826 documentos (34%), asi que toda agregacion temporal debe
declarar su cobertura. `ViewSpec.nota` existe para eso.

Funciones puras, sin estado, sin E/S y sin tokens.
"""

from __future__ import annotations

import re
from typing import Any

#: Un ano plausible para este corpus. Se descartan cifras como 1024 o 4096, que
#: aparecen en textos tecnicos y no son fechas.
_ANIO = re.compile(r"(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)")

#: Nombre legible de cada fenomeno. En la metadata `fenomeno` es un ENTERO
#: (1, 2, 3); en el contrato de la API es "F1", "F2", "F3". Este es el unico
#: lugar que traduce entre ambos.
FENOMENOS: dict[int, str] = {
    1: "IA y Capacidades Estrategicas",
    2: "Seguridad del Entorno Espacial",
    3: "Dinamicas Territoriales",
}


def fenomeno_id(valor: Any) -> str | None:
    """Entero de la metadata -> id del contrato. `2` -> `"F2"`."""
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return None
    return f"F{n}" if n in FENOMENOS else None


def fenomeno_numero(valor: str | int | None) -> int | None:
    """Id del contrato -> entero de la metadata. `"F2"` -> `2`."""
    if isinstance(valor, int):
        return valor if valor in FENOMENOS else None
    if isinstance(valor, str) and valor.upper().startswith("F"):
        try:
            n = int(valor[1:])
        except ValueError:
            return None
        return n if n in FENOMENOS else None
    return None


def organizacion(fuente: str) -> str:
    """Organizacion que publico el documento, leida de la ruta.

    Devuelve cadena vacia si la ruta no tiene la profundidad esperada: mejor un
    vacio visible que una organizacion adivinada.
    """
    partes = [p for p in (fuente or "").split("/") if p]
    return partes[1] if len(partes) > 1 else ""


def anio(fuente: str) -> int | None:
    """Ano identificado en la ruta del documento, o None.

    None significa "no identificado", NUNCA "sin fecha": el documento puede
    tener fecha y no estar en su nombre de archivo.
    """
    m = _ANIO.search(fuente or "")
    return int(m.group(1)) if m else None


def enrich(row: dict[str, Any]) -> dict[str, Any]:
    """Anade las dimensiones derivadas a una fila de metadata.

    No modifica la fila original. Los campos derivados se anaden solo si se
    pudieron obtener, para que su ausencia sea distinguible de un valor vacio.
    """
    fuente = str(row.get("fuente", ""))
    derivados: dict[str, Any] = {}

    org = organizacion(fuente)
    if org:
        derivados["organizacion"] = org

    ano = anio(fuente)
    if ano is not None:
        derivados["anio"] = ano

    fid = fenomeno_id(row.get("fenomeno"))
    if fid:
        derivados["fenomeno_id"] = fid
        derivados["fenomeno_nombre"] = FENOMENOS[int(row["fenomeno"])]

    return {**row, **derivados}
