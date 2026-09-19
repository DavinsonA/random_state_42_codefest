"""El compositor: que vistas acompañan a la que pidio el usuario. CERO tokens.

La Especificacion evalua la **ejecucion dinamica** con el 55 % del Reto 2: que
el sistema active el componente correcto, con los datos correctos, ante cada
pregunta. Una sola grafica por pregunta cumple la letra; un tablero que ademas
abre la vista que la primera hace evidente cumple el proposito.

Lo que se prueba aqui es sobre todo cuando NO debe componer: una vista de mas
que el usuario no pidio y que no aporta angulo nuevo es ruido, y el ruido en un
tablero se paga en la evaluacion de los expertos.
"""

from __future__ import annotations

from src.agents.compositor import MAX_COMPLEMENTARIAS, componer
from src.agents.hallazgos import Fila
from src.api.contracts import ViewSpec

F1 = [
    Fila("Atlantic_Council", 186, ["F1-ATL-001"]),
    Fila("CSET_Georgetown", 127, ["F1-CSET-001"]),
    Fila("AI_Index_Stanford", 65, ["F1-AI-001"]),
    Fila("DAIO", 35, ["F1-DAIO-001"]),
    Fila("CENIA", 27, ["F1-CENIA-001"]),
]
POR_FENOMENO = [
    Fila("F3", 888, ["F3-A-001"]),
    Fila("F2", 479, ["F2-B-001"]),
    Fila("F1", 459, ["F1-C-001"]),
]


def _claves(vistas):
    return [(v.chart, v.group_by, tuple(v.fenomenos)) for v in vistas]


# -- la vista principal manda -----------------------------------------------


def test_la_vista_del_usuario_va_siempre_primera():
    """El usuario pidio algo concreto: eso no se reordena ni se sustituye."""
    principal = ViewSpec(chart="bar", group_by="organizacion", fenomenos=["F1"])
    vistas = componer(principal, F1)
    assert vistas[0].chart == "bar"
    assert vistas[0].group_by == "organizacion"
    assert vistas[0].fenomenos == ["F1"]


def test_nunca_se_devuelven_mas_de_las_permitidas():
    principal = ViewSpec(chart="bar", group_by="fenomeno")
    assert len(componer(principal, POR_FENOMENO)) <= 1 + MAX_COMPLEMENTARIAS


def test_ninguna_complementaria_repite_a_la_principal():
    """Dos paneles identicos ocupan sitio y no añaden un angulo."""
    principal = ViewSpec(chart="bar", group_by="organizacion", fenomenos=["F1"])
    vistas = componer(principal, F1)
    assert len(_claves(vistas)) == len(set(_claves(vistas)))


# -- cuando SI compone ------------------------------------------------------


def test_una_vista_por_fenomeno_abre_el_fenomeno_dominante():
    """Si F3 es la mitad del corpus, la pregunta siguiente del analista es
    "y que hay dentro de F3": el tablero la adelanta."""
    principal = ViewSpec(chart="bar", group_by="fenomeno")
    vistas = componer(principal, POR_FENOMENO)
    detalle = [v for v in vistas[1:] if v.fenomenos == ["F3"]]
    assert detalle, "no abrio el fenomeno dominante"
    assert detalle[0].group_by == "organizacion"


def test_una_vista_concentrada_ofrece_la_composicion():
    """Cuando dos fuentes acumulan el 68 %, la proporcion es la lectura."""
    principal = ViewSpec(chart="bar", group_by="organizacion", fenomenos=["F1"])
    charts = [v.chart for v in componer(principal, F1)[1:]]
    assert "donut" in charts


# -- cuando NO compone ------------------------------------------------------


def test_sin_filas_no_inventa_vistas():
    principal = ViewSpec(chart="bar", group_by="organizacion")
    assert componer(principal, []) == [principal]


def test_una_distribucion_plana_no_genera_complementarias_de_concentracion():
    planas = [Fila(f"org{i}", 100, [f"D-{i}"]) for i in range(8)]
    principal = ViewSpec(chart="bar", group_by="organizacion")
    assert "donut" not in [v.chart for v in componer(principal, planas)[1:]]


def test_una_vista_de_una_sola_cifra_no_se_acompaña():
    """Un KPI es una respuesta cerrada; rodearlo de graficas lo diluye."""
    principal = ViewSpec(chart="kpi", group_by="fenomeno")
    assert componer(principal, POR_FENOMENO) == [principal]


def test_toda_complementaria_es_un_viewspec_valido():
    """El esquema cerrado es una frontera de seguridad: el compositor no puede
    saltarsela por ser codigo nuestro."""
    principal = ViewSpec(chart="bar", group_by="fenomeno")
    for v in componer(principal, POR_FENOMENO):
        ViewSpec.model_validate(v.model_dump())


def test_las_complementarias_temporales_arrastran_el_aviso_de_cobertura():
    """Solo el 34 % de los documentos declara año: una serie sin ese aviso es
    una cifra engañosa, y el compositor no es excepcion."""
    principal = ViewSpec(chart="bar", group_by="fenomeno")
    for v in componer(principal, POR_FENOMENO):
        if v.chart == "timeline" or v.group_by == "anio":
            assert "34" in v.nota


def test_los_titulos_de_las_complementarias_llevan_tildes():
    """`voz.py`: el titulo lo lee un analista en el tablero. El vocabulario
    interno va sin tildes; lo que se muestra, no."""
    principal = ViewSpec(chart="bar", group_by="organizacion", fenomenos=["F1"])
    for v in componer(principal, F1)[1:]:
        assert "organizacion" not in v.titulo, v.titulo


# -- mas angulos, sin relleno -----------------------------------------------


def test_ofrece_la_evolucion_anual_de_la_dimension_pedida():
    """`serie_por` cruza dos dimensiones: el año contra lo que se pregunto.
    Responde "y esto cómo se reparte por año", que sigue a casi cualquier
    comparación."""
    principal = ViewSpec(chart="bar", group_by="organizacion", fenomenos=["F1"])
    temporales = [v for v in componer(principal, F1)[1:] if v.chart == "timeline"]
    assert temporales, "no ofrecio la evolucion anual"
    assert temporales[0].serie_por == "organizacion"
    assert "34" in temporales[0].nota, "una vista temporal sin su aviso de cobertura"


def test_el_cruce_temporal_no_se_ofrece_sobre_una_serie_temporal():
    """Cruzar el año consigo mismo no pinta nada."""
    principal = ViewSpec(chart="timeline", group_by="anio")
    assert not [v for v in componer(principal, F1)[1:] if v.chart == "timeline"]


def test_el_cruce_temporal_necesita_varias_categorias():
    """Una serie de una sola linea es una serie simple con pasos de mas."""
    principal = ViewSpec(chart="bar", group_by="organizacion")
    una = [Fila("Unica", 100, ["D-1"])]
    assert not [v for v in componer(principal, una)[1:] if v.chart == "timeline"]


def test_ofrece_la_composicion_por_formato():
    """Distingue la fuente que publica informes de la que publica datos."""
    principal = ViewSpec(chart="bar", group_by="organizacion", fenomenos=["F1"])
    apiladas = [v for v in componer(principal, F1)[1:] if v.chart == "stacked_bar"]
    assert apiladas and apiladas[0].serie_por == "formato"


def test_sigue_sin_pasarse_del_tope_con_las_reglas_nuevas():
    principal = ViewSpec(chart="bar", group_by="organizacion", fenomenos=["F1"])
    assert len(componer(principal, F1)) <= 1 + MAX_COMPLEMENTARIAS


def test_toda_complementaria_nueva_sigue_siendo_un_viewspec_valido():
    """Las reglas del componente valen tambien para lo que propone el compositor."""
    principal = ViewSpec(chart="bar", group_by="organizacion", fenomenos=["F1"])
    for v in componer(principal, F1):
        revalidada = ViewSpec.model_validate(v.model_dump())
        assert revalidada.chart == v.chart
        assert revalidada.group_by == v.group_by, "la regla del grafico corrigio la dimension"


def test_una_serie_temporal_no_se_acompana_de_una_dona_de_anios():
    """La dona por ano no existe (REGLAS_GRAFICO): salia como un anillo de una sola porcion."""
    principal = ViewSpec(chart="timeline", group_by="anio", titulo="Documentos por ano")
    concentradas = [Fila("2025", 90), Fila("2024", 60), Fila("2023", 5), Fila("2022", 3), Fila("2021", 2)]
    vistas = componer(principal, concentradas)
    assert not any(v.chart == "donut" for v in vistas)
