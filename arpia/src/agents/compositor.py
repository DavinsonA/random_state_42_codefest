"""Compositor: que vistas acompañan a la que pidio el usuario. CERO tokens.

**Que problema resuelve.** El visualizador emite UNA vista por pregunta. Eso
responde la pregunta literal y deja al analista haciendo clic para llegar a lo
siguiente. La Especificacion evalua la ejecucion dinamica con el 55 % del
Reto 2 —"que el agente active el componente correcto, con los datos correctos,
ante cada pregunta"—, y un tablero que ademas abre la vista que la primera hace
evidente responde la pregunta que venia detras.

**Por que determinista.** Las complementarias se deducen de la forma de los
datos, no del significado de la pregunta: si una categoria acumula la mitad del
conjunto, mirar dentro de esa categoria es lo siguiente, y eso no hace falta
preguntarselo a un modelo. Cuesta cero tokens y no puede alucinar una vista que
el tablero no sepa poblar.

**Por que calla tan a menudo.** Una vista de mas que nadie pidio y que no añade
angulo es ruido, y un tablero ruidoso se lee peor que uno escueto. Cada regla
tiene su umbral y la mayoria de las veces no se cumple; la lista de casos en los
que NO compone es mas larga que la de los que si, y esta puesta a proposito.

El resultado se valida contra `ViewSpec`: el vocabulario cerrado es una frontera
de seguridad, y no deja de serlo porque quien la cruce sea codigo nuestro.
"""

from __future__ import annotations

from src.agents.hallazgos import (
    MIN_CATEGORIAS,
    NOMBRE_DIMENSION,
    UMBRAL_CONCENTRACION,
    UMBRAL_DOMINANCIA,
    Fila,
)
from src.api.contracts import ViewSpec

#: Vistas de apoyo por respuesta, ademas de la principal. Con mas, el tablero
#: deja de tener una lectura y pasa a ser una pared de graficas.
MAX_COMPLEMENTARIAS = 2

#: Id del agente en la traza y en `agentes_invocados`. Cuesta cero tokens, y
#: un agente que trabaja y no aparece es credito perdido.
AGENTE = "agente_compositor"

#: Dimension a la que se baja cuando se abre una categoria dominante: quien
#: publica es la pregunta util dentro de un fenomeno.
DIMENSION_DETALLE = "organizacion"

#: Se impone en toda vista temporal. No se confia en que nadie lo recuerde.
AVISO_COBERTURA = "Cobertura temporal: solo el 34% de los documentos declara año."

#: Graficos que responden algo cerrado. Rodear una sola cifra de graficas la
#: diluye en vez de explicarla.
CHARTS_SIN_APOYO = ("kpi", "table")


def _clave(v: ViewSpec) -> tuple:
    """Identidad de una vista, para no proponer dos veces lo mismo."""
    return (v.chart, v.group_by, tuple(v.fenomenos), v.metrica)


def _detalle_del_dominante(principal: ViewSpec, ordenadas: list[Fila], total: int) -> ViewSpec | None:
    """Si una categoria domina, abrirla por dentro.

    Solo aplica cuando se agrupo por fenomeno: bajar de un fenomeno a sus
    organizaciones es una pregunta real. Bajar de una organizacion a otra
    dimension no lo es.
    """
    if principal.group_by != "fenomeno" or principal.fenomenos:
        return None
    primera = ordenadas[0]
    if primera.valor / total < UMBRAL_DOMINANCIA:
        return None
    if primera.clave not in ("F1", "F2", "F3"):
        return None
    return ViewSpec(
        chart="bar",
        metrica=principal.metrica,
        fenomenos=[primera.clave],
        group_by=DIMENSION_DETALLE,
        titulo=f"Quién publica dentro de {primera.clave}",
    )


def _composicion(principal: ViewSpec, ordenadas: list[Fila], total: int) -> ViewSpec | None:
    """Si el reparto esta concentrado, la proporcion es la lectura.

    Un `donut` solo se justifica cuando la pregunta es de proporcion sobre pocas
    categorias; cuando el reparto es plano, una barra ya lo cuenta mejor y esta
    vista no aparece.
    """
    if principal.chart == "donut" or len(ordenadas) < MIN_CATEGORIAS:
        return None
    if sum(f.valor for f in ordenadas[:2]) / total < UMBRAL_CONCENTRACION:
        return None
    return ViewSpec(
        chart="donut",
        metrica=principal.metrica,
        fenomenos=list(principal.fenomenos),
        group_by=principal.group_by,
        titulo=f"Proporción por {NOMBRE_DIMENSION.get(principal.group_by, principal.group_by)}",
    )


def componer(principal: ViewSpec, filas: list[Fila]) -> list[ViewSpec]:
    """La vista del usuario y, si los datos lo justifican, las que la explican.

    Args:
        principal: lo que emitio el visualizador. Va primera y no se toca.
        filas: los datos que esa vista cargo, para leer su forma.

    Returns:
        Una lista que empieza SIEMPRE por `principal`. Con mucha frecuencia es
        solo ella, y eso es correcto.
    """
    utiles = [f for f in filas if f.valor > 0]
    total = sum(f.valor for f in utiles)
    if not utiles or total <= 0 or principal.chart in CHARTS_SIN_APOYO:
        return [principal]

    ordenadas = sorted(utiles, key=lambda f: -f.valor)
    candidatas = [
        _detalle_del_dominante(principal, ordenadas, total),
        _composicion(principal, ordenadas, total),
    ]

    vistas = [principal]
    vistos = {_clave(principal)}
    for v in candidatas:
        if v is None or len(vistas) > MAX_COMPLEMENTARIAS:
            continue
        if v.chart == "timeline" or v.group_by == "anio":
            v.nota = v.nota or AVISO_COBERTURA
        if _clave(v) in vistos:
            continue
        vistos.add(_clave(v))
        vistas.append(v)
    return vistas
