"""Endpoints de soporte del tablero (Reto 2).

Los consume el HTML estatico de `src/ui/static/` (`dashboard.js`, `viewspec.js`,
`referencias.js`). No los evalua ADL directamente —lo que se evalua es que el
tablero muestre el componente correcto con los datos correctos— pero son la
unica via por la que esos datos llegan al navegador.

Dos reglas, las mismas que en `/chat`:

- **Ninguno devuelve 500.** Un fallo se reporta dentro de un 200 con
  `disponible: false` y su motivo. Un 500 en el tablero durante la demo se ve
  igual que un despliegue caido.
- **Todo dato es rastreable.** Cada cifra viene con los `doc_id` que la
  sustentan, y `/api/evidence/{chunk_id}` devuelve el fragmento exacto. Es el
  requisito de trazabilidad de `RETO.md`, y es lo que permite que un experto
  cuestione un numero y llegue a su fuente en dos clics.

Cero tokens: todo sale de la tabla de metadata y del indice local.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from src.config import get_logger, get_settings
from src.observability import tracing

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["tablero"])


def _error(motivo: str, **extra: Any) -> JSONResponse:
    """Degradacion legible. Siempre 200: el tablero distingue 'no hay dato' de
    'el servicio se cayo', y un 404 no permite esa distincion."""
    return JSONResponse(status_code=200, content={"disponible": False, "motivo": motivo, **extra})


#: Nombre de cada fenomeno tal como lo lee el analista.
NOMBRE_FENOMENO = {
    "F1": "IA y Capacidades Estratégicas",
    "F2": "Seguridad del Entorno Espacial",
    "F3": "Dinámicas Territoriales",
}


def _etiqueta_serie(serie_por: str | None, clave: str) -> str:
    if serie_por == "fenomeno" and clave in NOMBRE_FENOMENO:
        return f"{clave} · {NOMBRE_FENOMENO[clave]}"
    return "Total" if clave == "total" else clave.replace("_", " ")


@router.get("/components")
def components() -> JSONResponse:
    """Catalogo de componentes y dimensiones con datos reales detras.

    Lo consulta el tablero al arrancar para saber que puede pintar, y el agente
    visualizador antes de emitir un `ViewSpec`.
    """
    try:
        import json

        from src.api.contracts import REGLAS_GRAFICO
        from src.retrieval.aggregates import MAX_CATEGORIAS, MAX_SERIES
        from src.tools.analytics import componentes_disponibles

        # Las reglas van AQUI y no en `componentes_disponibles`: esa funcion tambien
        # es lo que lee el visualizador, y cambiar lo que el modelo lee mueve sus
        # decisiones (medido: un campo de mas cambio F3 por F1).
        catalogo = json.loads(componentes_disponibles())
        catalogo["reglas"] = REGLAS_GRAFICO
        catalogo["limites"] = {"categorias": MAX_CATEGORIAS, "series": MAX_SERIES}
        return JSONResponse(content=catalogo)
    except Exception as exc:  # noqa: BLE001 - el tablero nunca recibe un 500
        log.warning("catalogo no disponible: %s", exc)
        return _error(f"catalogo no disponible: {type(exc).__name__}")


@router.get("/aggregate")
def aggregate(
    metrica: str = Query("conteo_documentos"),
    group_by: str = Query("fenomeno"),
    fenomenos: str = Query("", description='Ids separados por coma: "F1,F2"'),
    organizacion: str = Query(""),
    desde: int | None = Query(None),
    hasta: int | None = Query(None),
    limite: int = Query(25, ge=1, le=100),
) -> JSONResponse:
    """Conteo agregado sobre la tabla de documentos.

    Es el endpoint que puebla casi todo el tablero. Devuelve tambien `cobertura`:
    cuantos documentos quedaron fuera por no tener el dato de la dimension
    pedida. Ese numero se muestra, no se esconde.
    """
    try:
        from src.retrieval import aggregates

        if not aggregates.disponible():
            return _error("el corpus aun no esta cargado en este despliegue")

        lista = [f.strip().upper() for f in fenomenos.split(",") if f.strip()]
        datos = aggregates.agregar(
            metrica=metrica,  # type: ignore[arg-type]
            group_by=group_by,  # type: ignore[arg-type]
            fenomenos=lista or None,  # type: ignore[arg-type]
            organizacion=organizacion or None,
            desde=desde,
            hasta=hasta,
            limite=limite,
        )
        return JSONResponse(content={"disponible": True, **datos})
    except Exception as exc:  # noqa: BLE001
        log.warning("agregacion fallida: %s", exc)
        return _error(f"agregacion no disponible: {type(exc).__name__}")


@router.get("/documentos")
def documentos(
    fenomeno: str = Query("", description='Ids separados por coma: "F1,F3"'),
    organizacion: str = Query(""),
    formato: str = Query(""),
    desde: int | None = Query(None),
    hasta: int | None = Query(None),
    limite: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
    """Los documentos detras de una cifra: lista paginada y filtrable.

    Cada fila de `/api/aggregate` trae solo una muestra de 10 `doc_id`. Esto es
    la lista completa —con los mismos filtros—, para abrir "todos los
    documentos de esta barra". `primer_chunk_id` enlaza a `/api/evidence` y
    `doc_id` a `/api/document/{doc_id}`: de la cifra al fragmento en dos clics.
    """
    try:
        from src.retrieval import aggregates

        if not aggregates.disponible():
            return _error("el corpus aun no esta cargado en este despliegue")

        lista = [f.strip().upper() for f in fenomeno.split(",") if f.strip()]
        invalidos = [f for f in lista if f not in ("F1", "F2", "F3")]
        if invalidos:
            return _error(f"fenomeno no valido: {', '.join(invalidos)} (usa F1, F2 o F3)")

        datos = aggregates.documentos(
            fenomenos=lista or None,  # type: ignore[arg-type]
            organizacion=organizacion or None,
            formato=formato or None,
            desde=desde,
            hasta=hasta,
            limite=limite,
            offset=offset,
        )
        aviso = ""
        if datos["excluidos_por_fecha"]:
            aviso = (
                f"El rango de anos deja fuera {datos['excluidos_por_fecha']} documentos, "
                "incluidos todos los que no declaran fecha."
            )
        return JSONResponse(content={"disponible": True, **datos, "aviso": aviso})
    except Exception as exc:  # noqa: BLE001 - el tablero nunca recibe un 500
        log.warning("lista de documentos fallida: %s", exc)
        return _error(f"documentos no disponibles: {type(exc).__name__}")


@router.get("/timeline")
def timeline(
    fenomenos: str = Query(""),
    desde: int | None = Query(None),
    hasta: int | None = Query(None),
) -> JSONResponse:
    """Serie anual de documentos.

    Granularidad anual porque es la unica que el corpus sostiene, y con la
    cobertura por delante: solo el 34% de los documentos declara ano. Una linea
    de tiempo que oculte eso convierte un conteo honesto en una cifra enganosa.
    """
    try:
        from src.retrieval import aggregates

        if not aggregates.disponible():
            return _error("el corpus aun no esta cargado en este despliegue")

        lista = [f.strip().upper() for f in fenomenos.split(",") if f.strip()]
        datos = aggregates.agregar(
            group_by="anio",
            fenomenos=lista or None,  # type: ignore[arg-type]
            desde=desde,
            hasta=hasta,
            limite=100,
        )
        filas = sorted(datos["filas"], key=lambda f: f["clave"])
        cobertura = datos["cobertura"]
        return JSONResponse(
            content={
                "disponible": True,
                "granularidad": "anio",
                "filas": filas,
                "total": datos["total"],
                "cobertura": cobertura,
                "aviso": (
                    f"{cobertura['sin_dato_en_la_dimension']} de "
                    f"{cobertura['documentos_en_dimension']} documentos no declaran ano "
                    "y no aparecen en esta serie."
                ),
            }
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("linea de tiempo fallida: %s", exc)
        return _error(f"linea de tiempo no disponible: {type(exc).__name__}")


def dimension_efectiva(vista: Any) -> str:
    """Por que dimension agrupa realmente una vista.

    Una vista temporal agrupa por año diga lo que diga el agente: es la unica
    granularidad que el corpus sostiene, y una linea de tiempo por organizacion
    no es una linea de tiempo (`REGLAS_GRAFICO`).

    Vive aqui, en una sola funcion, porque el criterio lo usan dos caminos
    —`POST /api/view` y el compositor del turno— y dos copias del mismo criterio
    divergen a la primera que alguien toque una.
    """
    if vista.chart == "timeline":
        return "anio"
    return vista.group_by or "fenomeno"


def filas_de_vista(vista: Any) -> list[dict[str, Any]]:
    """Resuelve un `ViewSpec` a sus filas agregadas. CERO tokens.

    Nunca lanza: sin indice o con una agregacion imposible devuelve una lista
    vacia, y quien llame decide que hacer. Es deliberado —lo usa el compositor
    en pleno turno, y un fallo al proponer una vista de apoyo no puede tumbar
    la respuesta que el usuario esta esperando.
    """
    from src.retrieval import aggregates

    if not aggregates.disponible():
        return []
    try:
        datos = aggregates.agregar(
            metrica=vista.metrica,
            group_by=dimension_efectiva(vista),  # type: ignore[arg-type]
            fenomenos=list(vista.fenomenos) or None,
            desde=int(vista.desde) if vista.desde else None,
            hasta=int(vista.hasta) if vista.hasta else None,
            limite=100,
        )
    except Exception as exc:  # noqa: BLE001 - frontera: nunca tumba el turno
        log.warning("no se pudieron resolver las filas de la vista: %s", exc)
        return []
    return list(datos.get("filas") or [])


def serie_efectiva(vista: Any, group_by: str) -> str | None:
    """Que dimension separa las series de una vista.

    Con `serie_por` explicito, esa. Sin el, una vista agrupada por otra cosa que
    el fenomeno trae una serie por fenomeno: es lo que los graficos apilan y
    colorean, y hasta ahora lo armaba la GUI con una peticion por fenomeno.
    """
    if getattr(vista, "serie_por", None):
        return vista.serie_por
    return "fenomeno" if group_by != "fenomeno" else None


def _a_fila(f: dict[str, Any]) -> Any:
    from src.agents.hallazgos import Fila

    return Fila(
        clave=str(f.get("clave", "")),
        valor=int(f.get("valor") or 0),
        doc_ids=[str(d) for d in (f.get("doc_ids") or [])],
    )


def apoyo_de_vista(vista: Any, crudas: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    """Vistas de apoyo y hallazgos de una vista ya agregada. CERO tokens.

    Es UN solo camino para `/chat` y `POST /api/view`: el chat lo usa al cerrar
    el turno y el tablero al pintar una vista que nacio de un clic. Si fueran
    dos copias, el mismo grafico diria cosas distintas segun de donde llegue.

    Returns:
        `(vistas, hallazgos)`. `vistas` empieza SIEMPRE por `vista`.
    """
    from src.agents import compositor, hallazgos

    filas = [_a_fila(f) for f in crudas]
    return compositor.componer(vista, filas), hallazgos.describir(filas, dimension_efectiva(vista))


def _hallazgo_json(h: Any) -> dict[str, Any]:
    return {"texto": h.texto, "soporte": list(h.soporte), "doc_ids": list(h.doc_ids)}


@router.post("/view")
def view(spec: dict[str, Any]) -> JSONResponse:
    """Resuelve un `ViewSpec` a los datos que el tablero debe pintar.

    Es el puente entre los dos retos. El chat genera un `ViewSpec` y enlaza al
    tablero con `#vista=<json>`; el tablero lo envia aqui y recibe la serie
    lista, con su cobertura y su nota.

    **Por que un endpoint y no que el tablero arme la consulta.** Traducir
    `ViewSpec` a parametros de agregacion exige saber que `timeline` agrupa por
    ano, que `kpi` no agrupa, y que el vocabulario cerrado es el que es. Si esa
    logica se escribe tambien en JavaScript, hay dos copias del mismo criterio
    en dos lenguajes, y la primera vez que una cambie el tablero pintara algo
    que el agente no pidio. Aqui se valida contra el MISMO esquema que emite el
    visualizador: lo que no pase la validacion no se pinta.

    Args:
        spec: el `ViewSpec` tal cual lo emitio el agente.

    Returns:
        La vista lista para pintar: `categorias` y `series` (una por fenomeno si
        no se agrupa por el), `hallazgos` con los `doc_id` que los sustentan,
        `complementarias` (vistas de apoyo, como `ViewSpec`), `cobertura` y `aviso`.
        Se conserva `filas`: cronologica en las vistas temporales, de mayor a
        menor en el resto.
    """
    from pydantic import ValidationError

    from src.api.contracts import ViewSpec
    from src.retrieval import aggregates

    try:
        vista = ViewSpec.model_validate(spec)
    except ValidationError as exc:
        log.warning("view_spec invalido: %s", exc.errors()[:2])
        return _error("la vista no es valida", detalle=[e.get("msg", "") for e in exc.errors()[:3]])

    if not aggregates.disponible():
        return _error("el corpus aun no esta cargado en este despliegue")

    group_by = dimension_efectiva(vista)

    try:
        datos = aggregates.agregar(
            metrica=vista.metrica,
            group_by=group_by,  # type: ignore[arg-type]
            fenomenos=list(vista.fenomenos) or None,
            desde=int(vista.desde) if vista.desde else None,
            hasta=int(vista.hasta) if vista.hasta else None,
            limite=100,
        )
    except Exception as exc:  # noqa: BLE001 - el tablero nunca recibe un 500
        log.warning("no se pudo resolver la vista: %s", exc)
        return _error(f"datos no disponibles: {type(exc).__name__}")

    temporal = group_by == "anio"
    filas = sorted(datos["filas"], key=lambda f: f["clave"]) if temporal else datos["filas"]

    cobertura = datos["cobertura"]
    universo = cobertura["documentos_en_dimension"]

    # La nota del agente no reemplaza al dato medido: el numero va primero.
    # Y se avisa SIEMPRE que se hayan perdido documentos, sea la vista temporal
    # o no: un rango de anos sobre un conteo por organizacion borra a todo el
    # que no declare fecha, y la grafica sale creible y falsa.
    medidos: list[str] = []
    if temporal and cobertura["sin_dato_en_la_dimension"]:
        medidos.append(
            f"{cobertura['sin_dato_en_la_dimension']} de {universo} documentos "
            "no declaran ano y no aparecen en esta vista."
        )
    elif cobertura["excluidos_por_fecha"]:
        medidos.append(
            f"El rango de anos deja fuera {cobertura['excluidos_por_fecha']} de "
            f"{universo} documentos, incluidos todos los que no declaran fecha."
        )
    aviso = " ".join([*medidos, vista.nota]).strip()

    desde = int(vista.desde) if vista.desde else None
    hasta = int(vista.hasta) if vista.hasta else None
    serie_por = serie_efectiva(vista, group_by)

    # Lo que hay detras de una vista es apoyo: si falla, la vista sale igual.
    try:
        matriz = aggregates.agregar_series(
            metrica=vista.metrica,
            group_by=group_by,  # type: ignore[arg-type]
            serie_por=serie_por,  # type: ignore[arg-type]
            fenomenos=list(vista.fenomenos) or None,
            desde=desde,
            hasta=hasta,
            limite=vista.limite,
        )
        vistas, hallazgos = apoyo_de_vista(vista, datos["filas"])
    except Exception as exc:  # noqa: BLE001 - el tablero nunca recibe un 500
        log.warning("la vista %s salio sin series ni hallazgos: %s", vista.chart, exc)
        matriz, vistas, hallazgos = None, [vista], []

    return JSONResponse(
        content={
            "disponible": True,
            "chart": vista.chart,
            "titulo": vista.titulo,
            "metrica": vista.metrica,
            "group_by": group_by,
            "serie_por": serie_por,
            "fenomenos": list(vista.fenomenos),
            "categorias": matriz["categorias"] if matriz else [],
            "series": [
                {**s, "etiqueta": _etiqueta_serie(serie_por, s["clave"])} for s in matriz["series"]
            ]
            if matriz
            else [],
            "categorias_omitidas": matriz["categorias_omitidas"] if matriz else 0,
            "series_omitidas": matriz["series_omitidas"] if matriz else 0,
            "filas": filas,
            "total": datos["total"],
            "cobertura": cobertura,
            "aviso": aviso,
            "hallazgos": [_hallazgo_json(h) for h in hallazgos],
            "complementarias": [v.model_dump(exclude_none=True) for v in vistas[1:]],
        }
    )


@router.get("/geo")
def geo() -> JSONResponse:
    """Datos geograficos. **No disponibles, y es un hecho del corpus.**

    La metadata tiene ocho campos: `doc_id`, `chunk_id`, `fuente`, `formato`,
    `fenomeno`, `posicion`, `num_tokens` y `texto`. No hay lugar, ni pais, ni
    coordenadas. Extraerlos del texto exigiria procesar 326.866 fragmentos con
    un modelo, que no cabe en el presupuesto ni en el reloj.

    Existe y responde 200 a proposito: el tablero puede preguntar y recibir un
    "no hay dato" explicito, en vez de un 404 que se confunde con un fallo de
    despliegue. Inventar una ubicacion seria peor que las dos cosas, y
    `RETO.md` lo prohibe.
    """
    return _error(
        "el corpus no contiene ubicacion: la metadata no tiene lugar, pais ni coordenadas",
        alternativa=(
            "para analisis geografico se puede agrupar por organizacion, que es un "
            "dato real del corpus, pero indica quien publica y no donde ocurre"
        ),
    )


@router.get("/evidence/{chunk_id}")
def evidence(chunk_id: str) -> JSONResponse:
    """El fragmento exacto detras de una cita.

    Es lo que convierte una cita en evidencia verificable: el experto hace clic
    en `F2-SWF-120` y lee el texto que sustenta la afirmacion, con su
    procedencia. `RETO.md` lo exige para todo dato mostrado.
    """
    try:
        from src.tools.corpus import _get_index

        fila = _get_index().chunk(chunk_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("evidencia no accesible: %s", exc)
        return _error(f"indice no disponible: {type(exc).__name__}", chunk_id=chunk_id)

    if fila is None:
        return _error("fragmento no encontrado", chunk_id=chunk_id)

    return JSONResponse(
        content={
            "disponible": True,
            "chunk_id": fila.get("chunk_id"),
            "doc_id": fila.get("doc_id"),
            "texto": fila.get("texto", ""),
            "fuente": fila.get("fuente", ""),
            "organizacion": fila.get("organizacion", ""),
            "anio": fila.get("anio"),
            "formato": fila.get("formato", ""),
            "fenomeno": fila.get("fenomeno_id", ""),
            "fenomeno_nombre": fila.get("fenomeno_nombre", ""),
            "posicion": fila.get("posicion"),
            "total_fragmentos": fila.get("total_fragmentos"),
        }
    )


#: Fragmentos a cada lado del citado que se pueden pedir de una vez. Sin tope,
#: un solo GET podria devolver los 76.220 fragmentos de un CSV.
MAX_VENTANA = 10

#: Un fragmento llega a 18.000 tokens. En la vista del documento se recorta y se
#: avisa (`truncado`); el texto completo sigue en `/api/evidence/{chunk_id}`.
MAX_CHARS_FRAGMENTO = 4000


@router.get("/document/{doc_id}")
def document(
    doc_id: str,
    chunk_id: str | None = None,
    posicion: int | None = None,
    ventana: int = 2,
) -> JSONResponse:
    """El documento detras de una cita, reconstruido con sus fragmentos vecinos.

    Es el "ver el documento" de una referencia. El corpus guarda texto ya
    extraido, no el archivo original, asi que la vista es la misma para un PDF,
    un CSV o una pagina web: los fragmentos contiguos, con el citado marcado.
    Paginar es pedir de nuevo con otra `posicion`.

    Args:
        doc_id: documento (`F2-SWF-120`). Solo se usa como clave del indice,
            nunca como ruta de archivo.
        chunk_id: fragmento citado. Es el centro de la ventana y sale marcado
            `citado`. Debe pertenecer a `doc_id`.
        posicion: centro alternativo, cuando no hay fragmento citado. Por
            defecto 0 (el inicio del documento).
        ventana: fragmentos a cada lado del centro. Se recorta a 0..10.
    """
    ventana = max(0, min(ventana, MAX_VENTANA))
    try:
        from src.tools.corpus import _get_index

        indice = _get_index()
        total = indice.n_chunks(doc_id)
        if total is None:
            return _error("documento no encontrado", doc_id=doc_id)

        centro, citado = 0, None
        if chunk_id:
            fila = indice.chunk(chunk_id)
            if fila is None or fila.get("doc_id") != doc_id:
                return _error("el fragmento no pertenece a ese documento", doc_id=doc_id)
            centro, citado = int(fila.get("posicion", 0)), chunk_id
        elif posicion is not None:
            centro = max(0, min(posicion, total - 1))

        filas = indice.chunks_of(doc_id, centro - ventana, centro + ventana) or []
    except Exception as exc:  # noqa: BLE001
        log.warning("documento no accesible: %s", exc)
        return _error(f"indice no disponible: {type(exc).__name__}", doc_id=doc_id)

    if not filas:
        return _error("documento sin fragmentos", doc_id=doc_id)

    cabecera = filas[0]
    primero, ultimo = int(filas[0]["posicion"]), int(filas[-1]["posicion"])
    return JSONResponse(
        content={
            "disponible": True,
            "doc_id": doc_id,
            "formato": cabecera.get("formato", ""),
            "fuente": cabecera.get("fuente", ""),
            "organizacion": cabecera.get("organizacion", ""),
            "anio": cabecera.get("anio"),
            "fenomeno": cabecera.get("fenomeno_id", ""),
            "fenomeno_nombre": cabecera.get("fenomeno_nombre", ""),
            "total_fragmentos": total,
            "desde": primero,
            "hasta": ultimo,
            "hay_anterior": primero > 0,
            "hay_siguiente": ultimo < total - 1,
            "fragmentos": [
                {
                    "chunk_id": f["chunk_id"],
                    "posicion": f["posicion"],
                    "texto": str(f.get("texto", ""))[:MAX_CHARS_FRAGMENTO],
                    "truncado": len(str(f.get("texto", ""))) > MAX_CHARS_FRAGMENTO,
                    "citado": f["chunk_id"] == citado,
                }
                for f in filas
            ],
        }
    )


@router.get("/progress")
def progress(sesion: str = "") -> JSONResponse:
    """Por donde va el turno que esta corriendo ahora en esta sesion.

    Existe porque un turno tarda decenas de segundos y la interfaz solo podia
    mostrar un texto latiendo. Con esto ensena los agentes y las herramientas
    que ya reportaron, con datos reales: nada se estima ni se simula, y un paso
    solo aparece cuando su span cerro de verdad.

    **Abierto en produccion, y por eso NO devuelve contenido.** `GET /api/trace`
    esta cerrado tras `ARPIA_DEBUG_TRACE` porque los spans llevan el texto de la
    pregunta y los fragmentos del corpus. Este endpoint proyecta cada span sobre
    una lista blanca —identificador, padre, tipo, nombre y duracion— definida en
    `tracing.pasos_de_traza`, junto al propio `Span`, para que un campo nuevo no
    se publique solo el dia que alguien lo anada. Devolver aqui lo que alli se
    cerro seria publicarlo por la puerta de atras, en la URL que evalua ADL.

    Funciona porque `POST /chat` corre en el threadpool (`run_in_threadpool` en
    `main.py`): el bucle de eventos queda libre y este GET responde mientras el
    turno sigue en vuelo.

    Siempre 200, como el resto del modulo: es un adorno informativo, y la
    interfaz no debe distinguir "no hay turno" de un fallo.
    """
    if not sesion:
        return _error("falta el parametro `sesion`", pasos=[])

    trace_id = tracing.trace_de_sesion(sesion)
    if not trace_id:
        return _error("no hay ningun turno en curso para esa sesion", pasos=[])

    pasos = tracing.pasos_de_traza(trace_id)
    if pasos is None:
        return _error("la traza del turno ya no esta en memoria", pasos=[])

    return JSONResponse(content={"disponible": True, "trace_id": trace_id, "pasos": pasos})


@router.get("/trace/{trace_id}")
def trace(trace_id: str) -> JSONResponse:
    """Arbol de ejecucion de un turno: que se llamo, con que y cuanto tardo.

    **Cerrado salvo que `ARPIA_DEBUG_TRACE` este activo.** La traza contiene el
    texto de la pregunta del usuario, los fragmentos recuperados y la salida del
    modelo. Servir eso sin autenticacion en `agent.*` —el dominio que evalua
    ADL— es exposicion innecesaria, y el bloque de seguridad incluye analisis
    estatico de codigo.

    El `trace_id` es un uuid4 y no se puede adivinar, y no hay forma de
    enumerar las trazas por HTTP; pero "no se puede adivinar" no es un control
    de acceso. En desarrollo se enciende con la variable y sirve para explicar
    una respuesta rara despues de que ocurrio.
    """
    if not get_settings().debug_trace:
        return _error("la traza no se publica en este despliegue (ARPIA_DEBUG_TRACE)")

    spans = tracing.get_trace(trace_id)
    if spans is None:
        return _error("traza no disponible (solo se conservan las mas recientes)")
    return JSONResponse(content={"disponible": True, "trace_id": trace_id, "spans": spans})
