"""Vista de respaldo: cuando el visualizador intervino y no dejo una vista valida. CERO tokens.

**Que problema resuelve.** Medido contra el modelo real, `gpt-oss-20b` a veces
contesta en texto ("Lo siento, pero la categoria ... no esta disponible en los
parametros actuales") en vez de emitir el `ViewSpec`. Ese texto no valida, la
vista se descarta y el turno termina sin grafico: la dona de F3 salio en 1 de 3
redacciones de la misma pregunta. Sin vista tampoco corre el compositor, asi
que se pierden a la vez el grafico, sus vistas de apoyo y sus hallazgos.

**Por que se puede reconstruir sin modelo.** Cuando el orquestador planifico al
visualizador, ya decidio que el usuario quiere VER algo; y el analitico
--que corre en el mismo turno-- ya conto lo que hay que graficar y dejo sus
parametros en la traza (`consultar_agregado`: metrica, dimension y fenomeno). La
vista de respaldo es exactamente esa consulta con un tipo de grafico elegido por
las palabras de la pregunta. Es el mismo criterio que `plan_de_respaldo`:
degradar a algo determinista y util en vez de a una disculpa.

**Cuando NO actua.** Si el visualizador no intervino (el usuario no pidio una
vista) o si ya hay una vista valida. No inventa una vista para una pregunta de
texto: la garantia es "si se pidio un grafico, sale uno", no "siempre sale uno".

El resultado se valida contra `ViewSpec`: el vocabulario cerrado es una frontera
de seguridad, y no deja de serlo porque quien la cruce sea codigo nuestro.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import ValidationError

from src.agents.hallazgos import NOMBRE_DIMENSION
from src.api.contracts import ViewSpec

#: Agente cuya intervencion indica que el usuario pidio ver algo.
AGENTE_VISUALIZADOR = "agente_visualizador"

#: Tool del analitico donde quedan los parametros del conteo.
TOOL_CONTEO = "consultar_agregado"

#: Se impone en toda vista temporal (mismo texto que el compositor: una sola verdad).
AVISO_COBERTURA = "Cobertura temporal: solo el 34% de los documentos declara año."

_DONA = (
    "dona",
    "donut",
    "pastel",
    "torta",
    "proporcion",
    "porcentaje",
    "participacion",
    "que parte",
)
_LINEA = ("evolucion", "linea de tiempo", "serie", "tendencia", "a lo largo")
_TABLA = ("tabla",)
_APILADA = ("apilad",)
_KPI = ("una sola cifra", "un solo numero")

#: Lo que el corpus no tiene (lugar, mapa). Si el visualizador lo declino, NO se sustituye por
#: otra vista: una barra de "documentos por fenomeno" no responde a "muestrame un mapa".
_SIN_DATO = ("mapa", "geograf", "ubicacion", "donde ocurr", "coordenad", "red de actores")

#: El usuario pidio VER algo aunque el orquestador no haya llamado al visualizador.
_PIDE_VISTA = (
    "tabla",
    "grafic",
    "dona",
    "donut",
    "barras",
    "pastel",
    "torta",
    "visualiz",
    "linea de tiempo",
    "evolucion",
    "tendencia",
    "ha cambiado",
    "han cambiado",
    "a lo largo",
    "quiero ver",
    "una sola cifra",
)

#: Palabras que delatan un fenomeno cuando el conteo no lo dejo. Solo se usa si
#: EXACTAMENTE uno coincide: ante la duda, sin filtro (los tres) es lo honesto.
_FENOMENO = {
    "F1": ("inteligencia artificial", "capacidades estrategicas"),
    "F2": ("espacial", "espacio", "satelit", "orbita", "counterspace"),
    "F3": ("territorial", "territorio", "dinamicas territoriales"),
}


def _plano(texto: str) -> str:
    """Minusculas y sin tildes, solo para comparar palabras."""
    d = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def elegir_grafico(pregunta: str, group_by: str) -> str:
    """Tipo de grafico segun las palabras de la pregunta.

    Una serie por anio es siempre `timeline`: es la unica granularidad temporal
    que el corpus sostiene, y una dona por anios no dice nada.
    """
    p = _plano(pregunta)
    if any(w in p for w in _KPI):
        return "kpi"
    if group_by == "anio":
        return "timeline"
    if any(w in p for w in _TABLA):
        return "table"
    if any(w in p for w in _DONA):
        return "donut"
    if any(w in p for w in _APILADA):
        return "stacked_bar"
    if any(w in p for w in _LINEA):
        return "timeline"
    return "bar"


def _anio(valor: object) -> str | None:
    """`"2020"` -> `"2020"`; cualquier otra cosa, sin filtro (un ano mal escrito no tumba la vista)."""
    crudo = str(valor or "").strip()
    return crudo if len(crudo) == 4 and crudo.isdigit() else None


_RANGO = re.compile(
    r"\b(?:entre|de|del)\s+(?:el\s+)?((?:19|20)\d{2})\s+(?:y|a|al|hasta)\s+(?:el\s+)?((?:19|20)\d{2})\b"
)
_DESDE = re.compile(r"\b(?:desde|a partir de)\s+(?:el\s+)?((?:19|20)\d{2})\b")


def periodo_de_pregunta(pregunta: str) -> tuple[str | None, str | None]:
    """`("2020", "2025")` si la pregunta dice "entre 2020 y 2025"; `(None, None)` si no dice un periodo.

    El analista no siempre filtra por el periodo pedido: sin esto, "entre 2020 y 2025" se
    contesta con una vista que muestra todos los anos.
    """
    p = _plano(pregunta)
    if m := _RANGO.search(p):
        desde, hasta = sorted(m.groups())
        return desde, hasta
    if m := _DESDE.search(p):
        return m.group(1), None
    return None, None


_LIMITE = re.compile(r"\b(?:las|los|top|primeras|primeros|principales)\s+(\d{1,2})\b")
_TOPE_LIMITE = 25


def limite_de_pregunta(pregunta: str) -> int | None:
    """`5` si la pregunta pide "las 5 organizaciones que mas publican"; None si no pide un tope.

    `ViewSpec` no tiene un campo de limite que el modelo vea (medido: cada campo visible mueve
    sus decisiones), asi que el tope lo pone este codigo, que lee la pregunta.
    """
    if m := _LIMITE.search(_plano(pregunta)):
        n = int(m.group(1))
        return n if 1 <= n <= _TOPE_LIMITE else None
    return None


def fenomeno_de_pregunta(pregunta: str) -> list[str]:
    """`["F3"]` si la pregunta nombra un unico fenomeno; `[]` si ninguno o varios."""
    p = _plano(pregunta)
    hallados = [f for f, palabras in _FENOMENO.items() if any(w in p for w in palabras)]
    return hallados if len(hallados) == 1 else []


def _parametros_del_conteo(llamadas: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Parametros de la primera consulta del analitico, si hubo."""
    for llamada in llamadas:
        if llamada.get("name") == TOOL_CONTEO:
            return dict(llamada.get("input_parameters") or {})
    return None


def _dimension_de_pregunta(pregunta: str) -> str:
    from src.agents.executors import _dimension  # noqa: PLC0415 - modulo pesado, solo si hace falta

    return _dimension(pregunta)


def desde_turno(
    pregunta: str, agentes: list[str], llamadas: list[dict[str, Any]]
) -> ViewSpec | None:
    """La vista que el usuario pidio, reconstruida sin modelo. None si no aplica.

    Args:
        pregunta: lo que escribio el usuario (ya saneado por el guardian).
        agentes: agentes que intervinieron en el turno (`turnlog.agentes()`).
        llamadas: tools llamadas en el turno (`turnlog.tool_calls()`).
    """
    plano = _plano(pregunta)
    if any(w in plano for w in _SIN_DATO):
        return None

    conteo = _parametros_del_conteo(llamadas)
    # El visualizador intervino, o el usuario lo pidio con todas las letras y el analista ya
    # conto lo que hay que ver. Sin conteo y sin visualizador, no hay de donde sacar la vista.
    pidio_a_mano = conteo is not None and any(w in plano for w in _PIDE_VISTA)
    if AGENTE_VISUALIZADOR not in agentes and not pidio_a_mano:
        return None
    if conteo is not None:
        group_by = str(conteo.get("group_by") or "fenomeno")
        metrica = str(conteo.get("metrica") or "conteo_documentos")
        fenomeno = str(conteo.get("fenomenos") or "")
        fenomenos = [fenomeno] if fenomeno in ("F1", "F2", "F3") else []
        desde, hasta = (_anio(conteo.get(k)) for k in ("desde", "hasta"))
        if desde is None and hasta is None:
            desde, hasta = periodo_de_pregunta(pregunta)
    else:
        desde, hasta = periodo_de_pregunta(pregunta)
        group_by = _dimension_de_pregunta(pregunta)
        metrica = "conteo_documentos"
        fenomenos = fenomeno_de_pregunta(pregunta)

    chart = elegir_grafico(pregunta, group_by)
    limite = None
    if conteo is not None and str(conteo.get("limite") or "").isdigit():
        limite = int(conteo["limite"])
    elif chart not in ("kpi", "timeline"):
        limite = limite_de_pregunta(pregunta)
    unidad = "Fragmentos" if metrica == "conteo_fragmentos" else "Documentos"
    titulo = (
        f"{unidad} en total"
        if chart == "kpi"
        else f"{unidad} por {NOMBRE_DIMENSION.get(group_by, group_by)}"
    )
    if fenomenos:
        titulo += f" · {fenomenos[0]}"

    try:
        return ViewSpec(
            chart=chart,
            metrica=metrica,
            fenomenos=fenomenos,
            group_by=None if chart == "kpi" else group_by,
            limite=limite,
            desde=desde,
            hasta=hasta,
            titulo=titulo,
            nota=AVISO_COBERTURA if chart == "timeline" else "",
        )
    except ValidationError:
        return None
