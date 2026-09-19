"""Hallazgos: lo que los datos dicen, sin que nadie lo invente.

`RETO.md` §Restricciones duras: "Prohibido inventar puntajes. Ningun indice,
score de riesgo o nivel de amenaza calculado ad-hoc presentado como medicion
objetiva. Conteos, frecuencias y agregaciones si son validos."

Esa frontera es el contenido de este archivo. Un hallazgo puede decir que dos
organizaciones acumulan el 68 % de los documentos —es una frecuencia, se puede
recomputar y se puede rastrear a sus `doc_id`—. No puede decir que la
concentracion es "alta", que el riesgo "sube" ni que la serie "tiende" a algo:
eso son juicios que nadie midio, con la autoridad de una cifra.
"""

from __future__ import annotations

import pytest

from src.agents.hallazgos import Fila, describir

F1 = [
    Fila("Atlantic_Council", 186, ["F1-ATL-001", "F1-ATL-002"]),
    Fila("CSET_Georgetown", 127, ["F1-CSET-001"]),
    Fila("AI_Index_Stanford", 65, ["F1-AI-001"]),
    Fila("DAIO", 35, ["F1-DAIO-001"]),
    Fila("CENIA", 27, ["F1-CENIA-001"]),
    Fila("ILIA_Latam", 10, ["F1-ILIA-001"]),
    Fila("RutaN_GEIAL", 7, ["F1-RUTAN-001"]),
    Fila("Defensa21_LatAm", 2, ["F1-DEF-001"]),
]


# -- la frontera que no se cruza --------------------------------------------


@pytest.mark.parametrize(
    "prohibido",
    [
        "riesgo",
        "amenaza",
        "indice",
        "índice",
        "score",
        "puntaje",
        "nivel",
        "tendencia",
        "tendencial",
        "proyecc",
        "se espera",
        "probable",
        "preocupante",
        "alarmante",
        "critico",
        "crítico",
        "grave",
    ],
)
def test_ningun_hallazgo_emite_juicios_ni_pronosticos(prohibido):
    texto = " ".join(h.texto for h in describir(F1, "organizacion")).lower()
    assert prohibido not in texto, f"un hallazgo usa '{prohibido}'"


def test_cada_hallazgo_es_recomputable_desde_las_filas():
    """Si una cifra no se puede rehacer sumando las filas, es inventada."""
    for h in describir(F1, "organizacion"):
        assert h.soporte, f"hallazgo sin datos que lo sostengan: {h.texto}"
        for clave in h.soporte:
            assert any(f.clave == clave for f in F1), f"{clave} no esta en las filas"


def test_los_hallazgos_arrastran_los_doc_ids_que_los_sustentan():
    """`RETO.md`: todo dato mostrado debe rastrearse hasta su `doc_id`."""
    for h in describir(F1, "organizacion"):
        assert h.doc_ids, f"hallazgo sin procedencia: {h.texto}"


# -- lo que si debe decir ---------------------------------------------------


def test_detecta_la_concentracion_como_frecuencia_no_como_juicio():
    textos = [h.texto for h in describir(F1, "organizacion")]
    concentracion = [t for t in textos if "68" in t or "69" in t]
    assert concentracion, f"no detecto que dos fuentes acumulan el 68%: {textos}"


def test_nombra_la_categoria_dominante_con_su_cifra_exacta():
    textos = " ".join(h.texto for h in describir(F1, "organizacion"))
    assert "Atlantic Council" in textos or "Atlantic_Council" in textos
    assert "186" in textos


def test_una_distribucion_plana_no_inventa_un_hallazgo_de_concentracion():
    """El hallazgo tiene que ser falsable: si los datos estan repartidos, no
    aparece. Uno que sale siempre no informa de nada."""
    planas = [Fila(f"org{i}", 100, [f"D-{i}"]) for i in range(10)]
    textos = " ".join(h.texto for h in describir(planas, "organizacion")).lower()
    assert "acumulan" not in textos


def test_sin_filas_no_hay_hallazgos_y_no_revienta():
    assert describir([], "organizacion") == []


def test_una_sola_fila_no_produce_comparaciones():
    """Comparar una categoria consigo misma no dice nada."""
    uno = [Fila("Unica", 42, ["D-1"])]
    for h in describir(uno, "organizacion"):
        assert "acumulan" not in h.texto.lower()


def test_el_anio_recibe_el_aviso_de_cobertura_y_no_una_tendencia():
    """La dimension temporal es la mas facil de convertir en pronostico."""
    anios = [Fila("2024", 42, ["D-1"]), Fila("2025", 60, ["D-2"]), Fila("2026", 102, ["D-3"])]
    textos = " ".join(h.texto for h in describir(anios, "anio")).lower()
    assert "tendencia" not in textos and "crece" not in textos and "aumenta" not in textos


def test_los_hallazgos_estan_acotados_en_numero():
    """Un panel con quince frases no se lee. AGENTS.md §8: nada sin tope."""
    from src.agents.hallazgos import MAX_HALLAZGOS

    assert len(describir(F1, "organizacion")) <= MAX_HALLAZGOS


# -- forma del texto --------------------------------------------------------


def test_los_miles_no_se_comen_la_puntuacion_de_la_frase():
    """Formatear con un replace global sobre la frase convertia "(49 %), la
    cifra" en "(49 %). la cifra". Un producto con la puntuacion rota se lee como
    un producto descuidado."""
    textos = [h.texto for h in describir(F1, "organizacion")]
    for t in textos:
        assert ". la " not in t and ". frente" not in t, t
        assert "1,826" not in t and "459," not in t, f"miles sin formatear: {t}"


def test_el_texto_lleva_tildes():
    """`voz.py`: el texto que lee el usuario lleva tildes."""
    textos = " ".join(h.texto for h in describir(F1, "organizacion"))
    assert "mas alta" not in textos, "falta la tilde de 'más'"
    assert "categorias" not in textos, "falta la tilde de 'categorías'"
    assert "organizacion" not in textos, "la dimensión se nombra sin tilde"
    anios = [
        Fila("2024", 42, ["D-1"]),
        Fila("2025", 60, ["D-2"]),
        Fila("2026", 102, ["D-3"]),
        Fila("2023", 5, ["D-4"]),
    ]
    assert "ano con" not in " ".join(h.texto for h in describir(anios, "anio"))


def test_una_sola_categoria_no_produce_hallazgos():
    """ "Concentra el 100 %" con una categoria no informa: no hay con que comparar."""
    assert describir([Fila("F2", 479, ["F2-A"])], "fenomeno") == []
