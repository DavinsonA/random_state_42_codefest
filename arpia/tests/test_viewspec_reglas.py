"""El `ViewSpec` aplica las reglas que el propio modulo declara.

`REGLAS_GRAFICO` dice que dimensiones admite cada componente: un `donut` reparte
proporciones de pocas categorias y no tiene sentido por año, un `timeline` se
lee sobre el eje temporal y no sobre organizaciones. Esas reglas existian y se
publicaban en `/api/components`, pero el esquema no las aplicaba: aceptaba
`donut` por año tal cual y el tablero recibia una combinacion que sus propias
reglas declaran imposible.

**Se corrige, no se rechaza.** Es el mismo criterio que ya rige para
`serie_por`: una vista degradada es util, y una vista descartada por un campo
mal elegido deja al analista sin grafico. El modelo acierta el componente mucho
mas a menudo que la dimension, asi que manda el componente y la dimension se
ajusta al valor por defecto que la regla declara.
"""

from __future__ import annotations

import pytest

from src.api.contracts import REGLAS_GRAFICO, ViewSpec


@pytest.mark.parametrize("chart", sorted(REGLAS_GRAFICO))
def test_toda_vista_acaba_con_una_dimension_que_su_grafico_admite(chart):
    """Barrido sobre el catalogo entero: ninguna combinacion sobrevive invalida."""
    permitidas = REGLAS_GRAFICO[chart]["group_by"]
    for propuesta in ("fenomeno", "organizacion", "fuente", "formato", "anio"):
        v = ViewSpec.model_validate({"chart": chart, "group_by": propuesta})
        if v.group_by is not None:
            assert v.group_by in permitidas, f"{chart} quedo con group_by={v.group_by}"


def test_una_dimension_valida_se_respeta():
    """La correccion solo actua cuando hace falta: no reescribe buenas decisiones."""
    v = ViewSpec.model_validate({"chart": "bar", "group_by": "organizacion"})
    assert v.group_by == "organizacion"


def test_la_dona_por_año_cae_al_valor_por_defecto_de_su_regla():
    v = ViewSpec.model_validate({"chart": "donut", "group_by": "anio"})
    assert v.group_by == REGLAS_GRAFICO["donut"]["por_defecto"]


def test_la_serie_temporal_se_lee_sobre_el_eje_del_tiempo():
    v = ViewSpec.model_validate({"chart": "timeline", "group_by": "organizacion"})
    assert v.group_by in REGLAS_GRAFICO["timeline"]["group_by"]


def test_corregir_la_dimension_nunca_pierde_la_vista():
    """Lo que se protege: que el usuario reciba un grafico."""
    v = ViewSpec.model_validate(
        {"chart": "donut", "group_by": "anio", "titulo": "Proporción", "fenomenos": ["F2"]}
    )
    assert v.chart == "donut"
    assert v.titulo == "Proporción"
    assert v.fenomenos == ["F2"]


def test_la_dimension_mal_elegida_no_arrastra_el_cruce():
    """Si la dimension cambia, un `serie_por` que apuntaba a la nueva se anula:
    cruzar una dimension consigo misma no pinta nada."""
    v = ViewSpec.model_validate(
        {"chart": "donut", "group_by": "anio", "serie_por": REGLAS_GRAFICO["donut"]["por_defecto"]}
    )
    assert v.serie_por is None or v.serie_por != v.group_by
