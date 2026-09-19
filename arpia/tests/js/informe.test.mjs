import assert from "node:assert/strict";
import test from "node:test";

import { informeMarkdown } from "../../src/ui/static/js/informe.js";

const DATOS = {
    respuesta: "Conteo por organización:\n- CSIS_Aerospace: 214 documentos",
    hallazgos: ["CSIS Aerospace y SWF acumulan 349 de 479 documentos (73 %)."],
    hallazgos_detalle: [{ texto: "x", soporte: ["CSIS_Aerospace"], doc_ids: ["F2-CSIS-014"] }],
    citations: [{
        doc_id: "F2-SWF-120", chunk_id: "F2-SWF-120__chunk_000023",
        organizacion: "SWF Counterspace", fenomeno_nombre: "Seguridad del Entorno Espacial",
        anio: 2026, formato: "pdf", posicion: 23, total_fragmentos: 67,
    }],
    metadata: { tokens: { total: 3121 }, agentes_invocados: ["orquestador"] },
};

test("el informe lleva la pregunta y la respuesta que se vieron", () => {
    const md = informeMarkdown("Quién publica sobre seguridad espacial", DATOS);
    assert.match(md, /Quién publica sobre seguridad espacial/);
    assert.match(md, /CSIS_Aerospace: 214 documentos/);
});

test("toda cita llega con su doc_id y su chunk_id", () => {
    // RETO.md: todo dato mostrado se rastrea hasta su origen. Un informe sin
    // esos identificadores no sirve como anexo de un análisis.
    const md = informeMarkdown("x", DATOS);
    assert.match(md, /F2-SWF-120/);
    assert.match(md, /F2-SWF-120__chunk_000023/);
});

test("la cita se identifica por organización, no por la ruta del archivo", () => {
    const md = informeMarkdown("x", DATOS);
    assert.match(md, /SWF Counterspace/);
    assert.match(md, /Seguridad del Entorno Espacial/);
});

test("los hallazgos arrastran los documentos que los sustentan", () => {
    const md = informeMarkdown("x", DATOS);
    assert.match(md, /73 %/);
    assert.match(md, /F2-CSIS-014/);
});

test("una respuesta sin hallazgos ni citas no inventa secciones vacías", () => {
    const md = informeMarkdown("x", { respuesta: "Sin evidencia.", metadata: {} });
    assert.ok(!md.includes("## Fuentes"));
    assert.ok(!md.includes("## Lo que dicen las cifras"));
});

test("las vistas se listan con su nota de cobertura", () => {
    const md = informeMarkdown("x", DATOS, {
        vistas: [{ chart: "timeline", group_by: "anio", titulo: "Evolución", nota: "Cobertura: 34%" }],
    });
    assert.match(md, /Evolución/);
    assert.match(md, /Cobertura: 34%/);
});

test("no revienta con una respuesta incompleta", () => {
    assert.doesNotThrow(() => informeMarkdown("", {}));
    assert.doesNotThrow(() => informeMarkdown("", { citations: null, hallazgos: null }));
});
