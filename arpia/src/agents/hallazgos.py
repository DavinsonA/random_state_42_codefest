"""Hallazgos deterministas sobre una agregacion. CERO tokens.

**Que es un hallazgo aqui.** Una frase que describe algo que las cifras ya
dicen, y que cualquiera puede rehacer sumando las mismas filas. "Dos
organizaciones acumulan el 68 % de los 459 documentos" es un hallazgo: es una
frecuencia, se recomputa y se rastrea hasta sus `doc_id`.

**Que NO es.** `RETO.md` §Restricciones duras prohibe "ningun indice, score de
riesgo o nivel de amenaza calculado ad-hoc presentado como medicion objetiva".
Asi que este modulo no califica, no pondera y no proyecta: no existe un "indice
de concentracion", la concentracion no es "alta" y una serie de anos no
"tiende" a nada. La diferencia entre reportar y opinar es justo lo que el reto
mide, y una etiqueta inventada con forma de numero es la manera mas facil de
cruzar esa linea sin darse cuenta.

**Por que deterministas y de cero tokens.** Porque se puede. Los hallazgos
salen de aritmetica sobre metadata ya agregada, no de inferencia sobre datos
arbitrarios: preguntarselos a un modelo costaria tokens, seria mas lento y
daria cifras aproximadas donde las exactas estan a una resta de distancia.

**Falsables por diseno.** Un hallazgo que aparece siempre no informa de nada.
Cada regla lleva un umbral y calla cuando no se cumple: sobre una distribucion
plana no se dice que hay concentracion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Tope de hallazgos por vista. Un panel con quince frases no se lee, y el
#: analista deja de mirarlo entero (AGENTS.md §8: nada sin tope).
MAX_HALLAZGOS = 3

#: Documentos que se citan como respaldo de un hallazgo. Es una muestra: la
#: lista completa sale de `/api/aggregate`.
MUESTRA_DOC_IDS = 3

#: Cuota del total desde la que la acumulacion de las dos primeras categorias
#: deja de ser el reparto esperable y pasa a ser un hecho que vale contar.
#: Con menos, la frase seria cierta y vacia.
UMBRAL_CONCENTRACION = 0.60

#: Cuota desde la que una sola categoria domina el conjunto.
UMBRAL_DOMINANCIA = 0.40

#: Cuantas categorias hacen falta para que hablar de concentracion signifique
#: algo. Con tres, decir que dos acumulan el 70 % es casi una tautologia.
MIN_CATEGORIAS = 4

#: La dimension temporal es la que mas invita a convertir una serie en un
#: pronostico. Aqui solo se nombra el extremo, nunca la direccion.
DIMENSION_TEMPORAL = "anio"

#: Como se nombra cada dimension al usuario. El vocabulario interno va sin
#: tildes por compatibilidad con la metadata; el texto que se lee, no.
NOMBRE_DIMENSION = {
    "fenomeno": "fenómeno",
    "organizacion": "organización",
    "fuente": "fuente",
    "formato": "formato",
    "anio": "año",
}


@dataclass(frozen=True)
class Fila:
    """Una categoria de la agregacion con su conteo y su procedencia."""

    clave: str
    valor: int
    doc_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Hallazgo:
    """Una frase, las categorias de las que sale y los documentos que la sostienen.

    `soporte` existe para que el hallazgo sea auditable: dice sobre que filas se
    calculo, de modo que cualquiera pueda rehacer la cuenta.
    """

    texto: str
    soporte: tuple[str, ...]
    doc_ids: tuple[str, ...]


def _legible(clave: str) -> str:
    """`Atlantic_Council` es un identificador; `Atlantic Council` es un nombre."""
    return clave.replace("_", " ")


def _pct(parte: float, total: float) -> int:
    return round(100 * parte / total) if total else 0


def _miles(n: int) -> str:
    """1826 -> "1.826". Formatea SOLO el numero.

    Antes esto era un `.replace(",", ".")` sobre la frase entera, y se comia
    tambien las comas de la redaccion: "(49 %). la cifra mas alta". Un producto
    analitico con la puntuacion rota se lee como un producto descuidado.
    """
    return f"{n:,}".replace(",", ".")


def _muestra(filas: list[Fila]) -> tuple[str, ...]:
    ids: list[str] = []
    for f in filas:
        for d in f.doc_ids:
            if d not in ids:
                ids.append(d)
            if len(ids) >= MUESTRA_DOC_IDS:
                return tuple(ids)
    return tuple(ids)


def _dominancia(ordenadas: list[Fila], total: int, dimension: str) -> Hallazgo | None:
    """La categoria mayor, cuando de verdad destaca sobre el resto."""
    primera = ordenadas[0]
    cuota = primera.valor / total
    if cuota < UMBRAL_DOMINANCIA:
        return None
    return Hallazgo(
        texto=(
            f"{_legible(primera.clave)} concentra {_miles(primera.valor)} de los "
            f"{_miles(total)} documentos ({_pct(primera.valor, total)} %), la cifra "
            f"más alta por {NOMBRE_DIMENSION.get(dimension, dimension)}."
        ),
        soporte=(primera.clave,),
        doc_ids=_muestra([primera]),
    )


def _concentracion(ordenadas: list[Fila], total: int) -> Hallazgo | None:
    """Cuanto acumulan las dos primeras categorias frente al resto."""
    if len(ordenadas) < MIN_CATEGORIAS:
        return None
    dos = ordenadas[:2]
    suma = sum(f.valor for f in dos)
    if suma / total < UMBRAL_CONCENTRACION:
        return None
    nombres = " y ".join(_legible(f.clave) for f in dos)
    return Hallazgo(
        texto=(
            f"{nombres} acumulan {_miles(suma)} de {_miles(total)} documentos "
            f"({_pct(suma, total)} %), frente a {len(ordenadas) - 2} fuentes restantes."
        ),
        soporte=tuple(f.clave for f in dos),
        doc_ids=_muestra(dos),
    )


def _cola(ordenadas: list[Fila], total: int) -> Hallazgo | None:
    """Cuantas categorias aportan una fraccion marginal.

    Importa para leer la base de evidencia: una dimension con muchas categorias
    minimas no es tan diversa como su numero de categorias sugiere.
    """
    if len(ordenadas) < MIN_CATEGORIAS:
        return None
    marginales = [f for f in ordenadas if f.valor / total < 0.05]
    if len(marginales) < 2:
        return None
    suma = sum(f.valor for f in marginales)
    return Hallazgo(
        texto=(
            f"{len(marginales)} de {len(ordenadas)} categorías aportan menos del "
            f"5 % cada una y suman {_miles(suma)} documentos ({_pct(suma, total)} %)."
        ),
        soporte=tuple(f.clave for f in marginales),
        doc_ids=_muestra(marginales),
    )


def _extremo_temporal(ordenadas: list[Fila], total: int) -> Hallazgo | None:
    """El ano con mas documentos. **Solo el extremo, nunca la direccion.**

    Decir que la serie "crece" seria leer una tendencia en un corpus cuyo 66 %
    no declara ano: la curva describiria el trabajo de catalogacion, no el
    fenomeno. El extremo, en cambio, es un hecho del conjunto.
    """
    primera = ordenadas[0]
    return Hallazgo(
        texto=(
            f"El año con más documentos fechados es {primera.clave}, con "
            f"{_miles(primera.valor)} de {_miles(total)} ({_pct(primera.valor, total)} %)."
        ),
        soporte=(primera.clave,),
        doc_ids=_muestra([primera]),
    )


def describir(filas: list[Fila], dimension: str) -> list[Hallazgo]:
    """Hallazgos de una agregacion, de mas a menos informativo.

    Args:
        filas: categorias con su conteo. Se ordenan aqui, no se asume orden.
        dimension: por que se agrupo (`fenomeno`, `organizacion`, `anio`...).

    Returns:
        Como mucho `MAX_HALLAZGOS`. Lista vacia cuando no hay nada que decir,
        que es una respuesta legitima y frecuente.
    """
    utiles = [f for f in filas if f.valor > 0]
    total = sum(f.valor for f in utiles)
    if not utiles or total <= 0:
        return []

    ordenadas = sorted(utiles, key=lambda f: -f.valor)

    if dimension == DIMENSION_TEMPORAL:
        candidatos = [_extremo_temporal(ordenadas, total), _cola(ordenadas, total)]
    else:
        candidatos = [
            _concentracion(ordenadas, total),
            _dominancia(ordenadas, total, dimension),
            _cola(ordenadas, total),
        ]

    return [h for h in candidatos if h is not None][:MAX_HALLAZGOS]
