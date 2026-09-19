// Logica pura de las referencias (src/ui/static/js/referencias.js).
// Se corre con `node --test tests/js`; tests/test_frontend_referencias.py lo hace
// parte de la suite de pytest. El DOM (tooltip y visor) se prueba en el navegador.

import assert from "node:assert/strict";
import test from "node:test";

import {
    centroPagina,
    citaRecortada,
    describirCita,
    mensajeNoDisponible,
    partirPorReferencias,
} from "../../src/ui/static/js/referencias.js";

const ids = ["F2-SWF-117", "F1-AIINDEX-016"];

test("parte el texto y deja los identificadores como segmentos", () => {
    const partes = partirPorReferencias("Segun SWF (2019, F2-SWF-117), Rusia cuenta con sistemas.", ids);
    assert.deepEqual(partes, [
        { texto: "Segun SWF (2019, " },
        { id: "F2-SWF-117" },
        { texto: "), Rusia cuenta con sistemas." },
    ]);
});

test("reconoce varios identificadores, repetidos y pegados a la puntuacion", () => {
    const partes = partirPorReferencias("F2-SWF-117. Y F1-AIINDEX-016; otra vez F2-SWF-117", ids);
    assert.deepEqual(
        partes.filter((p) => p.id).map((p) => p.id),
        ["F2-SWF-117", "F1-AIINDEX-016", "F2-SWF-117"],
    );
});

test("no confunde un identificador con el prefijo o el sufijo de otro", () => {
    assert.deepEqual(partirPorReferencias("F2-SWF-1170 y XF2-SWF-117 y F2-SWF-117-2", ids), [
        { texto: "F2-SWF-1170 y XF2-SWF-117 y F2-SWF-117-2" },
    ]);
});

test("si un id contiene a otro gana el mas largo", () => {
    const partes = partirPorReferencias("ver F2-SWF-1170 aqui", ["F2-SWF-117", "F2-SWF-1170"]);
    assert.deepEqual(partes, [{ texto: "ver " }, { id: "F2-SWF-1170" }, { texto: " aqui" }]);
});

test("un id con caracteres de regex no rompe ni coincide de mas", () => {
    const raros = ["A.B(1)", "X+Y"];
    assert.deepEqual(partirPorReferencias("A.B(1) y AxB(1) y X+Y", raros), [
        { id: "A.B(1)" },
        { texto: " y AxB(1) y " },
        { id: "X+Y" },
    ]);
});

test("sin ids, o con texto vacio, no inventa segmentos", () => {
    assert.deepEqual(partirPorReferencias("hola", []), [{ texto: "hola" }]);
    assert.deepEqual(partirPorReferencias("", ids), []);
    assert.deepEqual(partirPorReferencias(null, ids), []);
});

test("describe la cita con su procedencia y su lugar en el documento", () => {
    const d = describirCita({ fuente: "SWF", anio: 2019, formato: "pdf", posicion: 11, total_fragmentos: 87 });
    assert.equal(d.origen, "SWF · 2019 · PDF");
    assert.equal(d.posicion, "Fragmento 12 de 87");
});

test("los campos que faltan simplemente no se muestran", () => {
    const d = describirCita({ fuente: "SWF" });
    assert.equal(d.origen, "SWF");
    assert.equal(d.posicion, "");
    assert.deepEqual(describirCita({}), { origen: "", posicion: "" });
});

test("la posicion 0 es valida y los miles usan el formato es-CO", () => {
    const d = describirCita({ posicion: 0, total_fragmentos: 76220 });
    assert.equal(d.posicion, "Fragmento 1 de 76.220");
});

test("la pagina siguiente y la anterior quedan pegadas a la ventana actual", () => {
    const doc = { desde: 10, hasta: 14 };
    assert.equal(centroPagina(doc, 1), 14 + 1 + 2);
    assert.equal(centroPagina(doc, -1), 10 - 1 - 2);
    assert.equal(centroPagina(doc, 1, 5), 14 + 1 + 5);
});

test("un fragmento que llega al largo maximo se marca como recortado", () => {
    assert.equal(citaRecortada({ fragmento: "x".repeat(240) }), true);
    assert.equal(citaRecortada({ fragmento: "corto" }), false);
    assert.equal(citaRecortada({}), false);
});

test("traduce los motivos del backend a mensajes legibles", () => {
    assert.match(mensajeNoDisponible("documento no encontrado"), /no está en el índice/);
    assert.match(mensajeNoDisponible("indice no disponible: FileNotFoundError"), /todavía no está disponible/);
    assert.match(mensajeNoDisponible("algo raro"), /No se pudo abrir/);
    assert.match(mensajeNoDisponible(undefined), /No se pudo abrir/);
});
