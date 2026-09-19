// Traduccion de POST /api/view a los datos del tablero (js/viewspec.js: `cargar`).
//
// Las respuestas simuladas tienen la forma REAL del backend (src/api/dashboard.py):
// filas `{clave, valor, doc_ids}` sin fenomeno y una cobertura con otros nombres.
// Antes el tablero esperaba `{grupo, fenomeno}` y `cobertura.{con_dato,total}`, asi
// que nunca pudo leer un dato real.

import assert from "node:assert/strict";
import test from "node:test";

import { VISTA_INICIAL, VISTA_TIEMPO_INICIAL, cargar, mensajeIndice, normalizar, tituloPorDefecto } from "../../src/ui/static/js/viewspec.js";

/** Instala un fetch falso. `responder(spec)` devuelve el cuerpo que daria `POST /api/view`. */
function simularBackend(responder) {
    const llamadas = [];
    globalThis.fetch = async (ruta, opciones = {}) => {
        const spec = opciones.body ? JSON.parse(opciones.body) : {};
        llamadas.push({ ruta: String(ruta), metodo: opciones.method, spec });
        return { ok: true, status: 200, json: async () => responder(spec) };
    };
    return llamadas;
}

const COBERTURA = (enDimension, sinDato) => ({
    documentos_universo: 1826,
    documentos_en_dimension: enDimension,
    documentos_contados: enDimension,
    sin_dato_en_la_dimension: sinDato,
    excluidos_por_fecha: 0,
});

/** Respuesta de `/api/view` con los valores por defecto de una vista simple. */
const VISTA = (o) => ({
    disponible: true,
    group_by: "fenomeno",
    serie_por: null,
    categorias: [],
    series: [],
    total: 0,
    cobertura: COBERTURA(1826, 0),
    aviso: "",
    ...o,
});

test("por año es UNA llamada a /api/view y cada fila hereda el fenómeno de su serie", async () => {
    const llamadas = simularBackend(() =>
        VISTA({
            group_by: "anio",
            serie_por: "fenomeno",
            categorias: ["2025"],
            series: [
                { clave: "F1", valores: [16], doc_ids: [["F1-A"]] },
                { clave: "F2", valores: [5], doc_ids: [["F2-A"]] },
                { clave: "F3", valores: [5], doc_ids: [["F3-A"]] },
            ],
            total: 26,
        }),
    );
    const { datos, error } = await cargar(normalizar(VISTA_TIEMPO_INICIAL));

    assert.equal(error, undefined);
    assert.equal(llamadas.length, 1, "una sola llamada, no una por fenómeno");
    assert.deepEqual([llamadas[0].ruta, llamadas[0].metodo], ["/api/view", "POST"]);
    assert.equal(llamadas[0].spec.chart, "timeline");
    assert.deepEqual(
        datos.filas.map((f) => [f.grupo, f.fenomeno, f.valor]),
        [["2025", "F1", 16], ["2025", "F2", 5], ["2025", "F3", 5]],
    );
    assert.deepEqual(datos.filas[0].doc_ids, ["F1-A"]);
    assert.equal(datos.total, 26);
    assert.equal(datos.simulado, false);
});

test("la cobertura del año sale de la del servidor: los que declaran año sobre los que podían", async () => {
    simularBackend(() => VISTA({ group_by: "anio", cobertura: COBERTURA(1826, 1205), aviso: "1205 de 1826 documentos no declaran ano" }));
    const { datos } = await cargar(normalizar(VISTA_TIEMPO_INICIAL));
    // con dato = 1826 - 1205 = 621 de 1.826; el aviso del servidor no se repite: lo dice la cobertura
    assert.deepEqual(datos.cobertura, { con_dato: 621, total: 1826 });
    assert.equal(datos.nota, "");
});

test("por fenómeno es una sola petición y la clave es el fenómeno", async () => {
    const llamadas = simularBackend(() =>
        VISTA({
            categorias: ["F3", "F2", "F1"],
            series: [{ clave: "total", valores: [888, 479, 459], doc_ids: [["F3-ALERTAS-001"], [], []] }],
            total: 1826,
        }),
    );
    const { datos } = await cargar(normalizar(VISTA_INICIAL));

    assert.equal(llamadas.length, 1);
    assert.equal(llamadas[0].spec.group_by, "fenomeno");
    assert.deepEqual(datos.filas.map((f) => [f.grupo, f.fenomeno]), [["F3", "F3"], ["F2", "F2"], ["F1", "F1"]]);
    assert.equal(datos.total, 1826);
});

test("fuera del año no hay cobertura: '100 % tienen año' sería falso", async () => {
    simularBackend(() =>
        VISTA({
            group_by: "organizacion",
            serie_por: "fenomeno",
            categorias: ["CSET"],
            series: [{ clave: "F1", valores: [3], doc_ids: [[]] }],
            total: 3,
        }),
    );
    const { datos } = await cargar(normalizar({ chart: "bar", group_by: "organizacion" }));
    assert.equal(datos.cobertura, null);
});

test("un aviso que no es del año (rango de años) sí llega al tablero", async () => {
    simularBackend(() => VISTA({ group_by: "organizacion", aviso: "El rango de anos deja fuera 1205 de 1826 documentos" }));
    const { datos } = await cargar(normalizar({ chart: "bar", group_by: "organizacion", desde: "2020" }));
    assert.match(datos.nota, /El rango de anos deja fuera 1205/);
});

test("el fenómeno, el filtro de años y la métrica viajan al backend en el ViewSpec", async () => {
    const llamadas = simularBackend(() => VISTA({ group_by: "anio" }));
    await cargar(normalizar({ chart: "timeline", fenomenos: ["F2"], metrica: "conteo_fragmentos", desde: "2020", hasta: "2024" }));
    const { spec } = llamadas[0];
    assert.deepEqual(
        [spec.fenomenos, spec.metrica, spec.desde, spec.hasta],
        [["F2"], "conteo_fragmentos", "2020", "2024"],
    );
});

test("si el índice no está devuelve un error legible y no datos inventados", async () => {
    simularBackend(() => ({ disponible: false, motivo: "indice no disponible: FileNotFoundError" }));
    const r = await cargar(normalizar(VISTA_INICIAL));
    assert.equal(r.datos, undefined);
    assert.match(r.error, /índice del corpus todavía no está disponible/);
});

test("solo en modo stub el índice caído cae a datos simulados, y marcados", async () => {
    simularBackend(() => ({ disponible: false, motivo: "indice no disponible: X" }));
    const { datos } = await cargar(normalizar(VISTA_INICIAL), { modoStub: true });
    assert.equal(datos.simulado, true);
});

test("un fallo de red se convierte en error, no en excepción", async () => {
    globalThis.fetch = async () => {
        throw new TypeError("network");
    };
    const r = await cargar(normalizar(VISTA_INICIAL));
    assert.match(r.error, /No se pudo conectar/);
});

test("mensajeIndice traduce el motivo del backend", () => {
    assert.match(mensajeIndice("indice no disponible: FileNotFoundError"), /todavía no está disponible/);
    assert.match(mensajeIndice("otra cosa"), /otra cosa/);
    assert.match(mensajeIndice(undefined), /No se pudieron cargar/);
});

// Una dona reparte un todo por cualquier dimension. `normalizar` la forzaba a
// `fenomeno`: la dona de "documentos por organizacion" salia como un anillo de
// una sola porcion, con el titulo de organizacion y los datos de fenomeno.
test("una dona conserva la dimension que pidio el agente", () => {
    for (const grupo of ["organizacion", "fuente", "formato", "fenomeno"]) {
        assert.equal(normalizar({ chart: "donut", group_by: grupo }).group_by, grupo);
    }
});

test("una dona sin dimension, o por anio, cae a fenomeno", () => {
    assert.equal(normalizar({ chart: "donut" }).group_by, "fenomeno");
    assert.equal(normalizar({ chart: "donut", group_by: "anio" }).group_by, "fenomeno");
});

test("la dona por organizacion pide UNA vista por organizacion, con el fenomeno filtrado", async () => {
    const llamadas = simularBackend(() =>
        VISTA({
            group_by: "organizacion",
            serie_por: "fenomeno",
            categorias: ["SIPRI"],
            series: [{ clave: "F3", valores: [4], doc_ids: [["a"]] }],
            total: 4,
        }),
    );
    const { datos } = await cargar(normalizar({ chart: "donut", group_by: "organizacion", fenomenos: ["F3"] }));
    assert.equal(llamadas.length, 1);
    assert.deepEqual([llamadas[0].spec.chart, llamadas[0].spec.group_by, llamadas[0].spec.fenomenos], ["donut", "organizacion", ["F3"]]);
    assert.deepEqual(datos.filas.map((f) => [f.grupo, f.fenomeno]), [["SIPRI", "F3"]]);
});

test("normalizar conserva serie_por solo donde se puede pintar", () => {
    assert.equal(normalizar({ chart: "stacked_bar", group_by: "organizacion", serie_por: "formato" }).serie_por, "formato");
    assert.equal(normalizar({ chart: "timeline", serie_por: "organizacion" }).serie_por, "organizacion");
    assert.equal(normalizar({ chart: "bar", group_by: "organizacion", serie_por: "organizacion" }).serie_por, null, "igual al eje");
    assert.equal(normalizar({ chart: "timeline", serie_por: "anio" }).serie_por, null, "el eje ya es el anio");
    assert.equal(normalizar({ chart: "donut", group_by: "organizacion", serie_por: "formato" }).serie_por, null);
    assert.equal(normalizar({ chart: "bar", group_by: "organizacion", serie_por: "lugar" }).serie_por, null);
    assert.equal(normalizar({ chart: "bar", group_by: "organizacion" }).serie_por, null);
});

test("una vista con serie_por se pide a /api/view y sus series llegan cruzadas", async () => {
    const pedidos = [];
    globalThis.fetch = async (url, opciones) => {
        pedidos.push([String(url), opciones?.method, opciones?.body]);
        return {
            ok: true,
            status: 200,
            headers: { get: () => "application/json" },
            json: async () => ({
                disponible: true,
                serie_por: "formato",
                categorias: ["SIPRI", "RESDAL"],
                series: [
                    { clave: "pdf", valores: [4, 0], doc_ids: [["a"], []] },
                    { clave: "csv", valores: [1, 3], doc_ids: [["b"], ["c"]] },
                ],
                total: 8,
                aviso: "",
            }),
        };
    };
    const spec = normalizar({ chart: "stacked_bar", group_by: "organizacion", serie_por: "formato", fenomenos: ["F3"] });
    const { datos } = await cargar(spec);
    assert.equal(pedidos.length, 1, "una sola llamada, no una por fenomeno");
    assert.deepEqual(pedidos[0].slice(0, 2), ["/api/view", "POST"]);
    assert.equal(JSON.parse(pedidos[0][2]).serie_por, "formato");
    assert.deepEqual(
        datos.filas.map((f) => [f.grupo, f.serie, f.valor, f.fenomeno]),
        [["SIPRI", "pdf", 4, null], ["SIPRI", "csv", 1, null], ["RESDAL", "csv", 3, null]],
        "las celdas en cero no se dibujan",
    );
    assert.equal(datos.total, 8);
});

test("si /api/view no esta disponible, el cruce lo dice en vez de inventar datos", async () => {
    globalThis.fetch = async () => ({
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        json: async () => ({ disponible: false, motivo: "el corpus aun no esta cargado en este despliegue" }),
    });
    const r = await cargar(normalizar({ chart: "timeline", serie_por: "organizacion" }));
    assert.ok(r.error && !r.datos);
});

test("el aviso del servidor no repite la nota que la vista ya trae", async () => {
    globalThis.fetch = async () => ({
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        json: async () => ({
            disponible: true,
            serie_por: "organizacion",
            categorias: ["2024"],
            series: [{ clave: "SIPRI", valores: [2], doc_ids: [["a"]] }],
            total: 2,
            aviso: "174 de 479 documentos no declaran ano. Cobertura temporal: solo el 34% declara ano.",
        }),
    });
    const spec = normalizar({ chart: "timeline", serie_por: "organizacion", nota: "Cobertura temporal: solo el 34% declara ano." });
    const { datos } = await cargar(spec);
    assert.equal(datos.nota, "174 de 479 documentos no declaran ano.");
});

test("normalizar conserva el tope de categorias solo si es valido", () => {
    assert.equal(normalizar({ chart: "table", group_by: "organizacion", limite: 5 }).limite, 5);
    assert.equal(normalizar({ chart: "table", group_by: "organizacion", limite: 500 }).limite, null);
    assert.equal(normalizar({ chart: "table", group_by: "organizacion" }).limite, null);
});

// El panel con el que abre el tablero: de que tipo es el material de cada fenomeno.
test("la vista inicial cruza fenomeno y formato, y normalizar no la desarma", () => {
    const v = normalizar(VISTA_INICIAL);
    assert.deepEqual([v.chart, v.group_by, v.serie_por], ["stacked_bar", "fenomeno", "formato"]);
    assert.equal(tituloPorDefecto(v), "Documentos por fenómeno y formato");
});

test("una barra apilada por fenomeno ya no se reescribe a organizacion", () => {
    assert.equal(normalizar({ chart: "stacked_bar", group_by: "fenomeno" }).group_by, "fenomeno");
    assert.equal(normalizar({ chart: "stacked_bar" }).group_by, "organizacion");
});
