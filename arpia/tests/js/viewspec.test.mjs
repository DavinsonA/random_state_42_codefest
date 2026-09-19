// Traduccion de /api/aggregate a los datos del tablero (js/viewspec.js: `cargar`).
//
// Las respuestas simuladas tienen la forma REAL del backend (src/api/dashboard.py):
// filas `{clave, valor, doc_ids}` sin fenomeno y una cobertura con otros nombres.
// Antes el tablero esperaba `{grupo, fenomeno}` y `cobertura.{con_dato,total}`, asi
// que nunca pudo leer un dato real.

import assert from "node:assert/strict";
import test from "node:test";

import { VISTA_INICIAL, VISTA_TIEMPO_INICIAL, cargar, mensajeIndice, normalizar } from "../../src/ui/static/js/viewspec.js";

/** Instala un fetch falso. `responder(params)` devuelve el cuerpo del backend. */
function simularBackend(responder) {
    const llamadas = [];
    globalThis.fetch = async (ruta) => {
        const url = new URL(ruta, "http://local");
        const params = Object.fromEntries(url.searchParams);
        llamadas.push({ ruta: url.pathname, params });
        return { ok: true, status: 200, json: async () => responder(params) };
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

test("por año pide una vez por fenómeno y cada fila hereda el suyo", async () => {
    const llamadas = simularBackend((p) => ({
        disponible: true,
        group_by: "anio",
        filas: [{ clave: "2025", valor: p.fenomenos === "F1" ? 16 : 5, doc_ids: [`${p.fenomenos}-A`] }],
        cobertura: COBERTURA(p.fenomenos === "F1" ? 459 : 700, p.fenomenos === "F1" ? 411 : 500),
    }));
    const spec = normalizar(VISTA_TIEMPO_INICIAL);
    const { datos, error } = await cargar(spec);

    assert.equal(error, undefined);
    assert.deepEqual(llamadas.map((l) => l.params.fenomenos), ["F1", "F2", "F3"]);
    assert.ok(llamadas.every((l) => l.ruta === "/api/aggregate" && l.params.group_by === "anio"));
    assert.deepEqual(
        datos.filas.map((f) => [f.grupo, f.fenomeno, f.valor]),
        [["2025", "F1", 16], ["2025", "F2", 5], ["2025", "F3", 5]],
    );
    assert.deepEqual(datos.filas[0].doc_ids, ["F1-A"]);
    assert.equal(datos.total, 26);
    assert.equal(datos.simulado, false);
});

test("la cobertura del año suma los tres fenómenos y usa los nombres del backend", async () => {
    simularBackend((p) => ({
        disponible: true,
        filas: [],
        cobertura: COBERTURA(...{ F1: [459, 411], F2: [479, 300], F3: [888, 494] }[p.fenomenos]),
    }));
    const { datos } = await cargar(normalizar(VISTA_TIEMPO_INICIAL));
    // con dato = (459-411) + (479-300) + (888-494) = 621 de 1.826
    assert.deepEqual(datos.cobertura, { con_dato: 621, total: 1826 });
});

test("por fenómeno es una sola petición y la clave es el fenómeno", async () => {
    const llamadas = simularBackend(() => ({
        disponible: true,
        filas: [
            { clave: "F3", valor: 888, doc_ids: ["F3-ALERTAS-001"] },
            { clave: "F2", valor: 479, doc_ids: [] },
            { clave: "F1", valor: 459, doc_ids: [] },
        ],
        cobertura: COBERTURA(1826, 0),
    }));
    const { datos } = await cargar(normalizar(VISTA_INICIAL));

    assert.equal(llamadas.length, 1);
    assert.equal(llamadas[0].params.group_by, "fenomeno");
    assert.deepEqual(datos.filas.map((f) => [f.grupo, f.fenomeno]), [["F3", "F3"], ["F2", "F2"], ["F1", "F1"]]);
    assert.equal(datos.total, 1826);
});

test("fuera del año no hay cobertura: '100 % tienen año' sería falso", async () => {
    simularBackend(() => ({ disponible: true, filas: [{ clave: "CSET", valor: 3, doc_ids: [] }], cobertura: COBERTURA(1826, 0) }));
    const { datos } = await cargar(normalizar({ chart: "bar", group_by: "organizacion" }));
    assert.equal(datos.cobertura, null);
});

test("un fenómeno pedido explícitamente hace una sola petición", async () => {
    const llamadas = simularBackend(() => ({ disponible: true, filas: [], cobertura: COBERTURA(459, 411) }));
    await cargar(normalizar({ chart: "timeline", fenomenos: ["F2"] }));
    assert.deepEqual(llamadas.map((l) => l.params.fenomenos), ["F2"]);
});

test("el filtro de años y la métrica viajan al backend", async () => {
    const llamadas = simularBackend(() => ({ disponible: true, filas: [], cobertura: COBERTURA(1, 0) }));
    await cargar(normalizar({ chart: "timeline", metrica: "conteo_fragmentos", desde: "2020", hasta: "2024" }));
    assert.deepEqual(
        [llamadas[0].params.metrica, llamadas[0].params.desde, llamadas[0].params.hasta],
        ["conteo_fragmentos", "2020", "2024"],
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
