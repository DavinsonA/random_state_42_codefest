// El informe en PDF (js/informe.js: `informePdf`). jsPDF se simula: aqui se prueba QUE se dibuja
// y con que orden, no el formato binario del PDF.

import assert from "node:assert/strict";
import test from "node:test";

globalThis.localStorage ??= { getItem: () => null, setItem: () => {} };
globalThis.window ??= {
    localStorage: globalThis.localStorage,
    location: { search: "", hash: "" },
    matchMedia: () => ({ matches: false }),
};
globalThis.document ??= {
    documentElement: {},
    addEventListener: () => {},
    querySelector: () => null,
    querySelectorAll: () => [],
};
globalThis.getComputedStyle = () => ({ getPropertyValue: () => "#0F1B30" });

const { informePdf } = await import("../../src/ui/static/js/informe.js");

/** jsPDF de mentira: anota cada texto e imagen que recibe. */
function jsPDFSimulado() {
    const eventos = { textos: [], imagenes: [], paginas: 1 };
    class Doc {
        constructor() {
            this.eventos = eventos;
        }
        setFont() { return this; }
        setFontSize() { return this; }
        setTextColor() { return this; }
        setFillColor() { return this; }
        setDrawColor() { return this; }
        setLineWidth() { return this; }
        rect() { return this; }
        roundedRect() { return this; }
        circle() { return this; }
        line() { return this; }
        setPage() { return this; }
        addPage() { eventos.paginas += 1; return this; }
        getNumberOfPages() { return eventos.paginas; }
        splitTextToSize(texto, ancho) {
            const palabras = String(texto).split(" ");
            const lineas = [];
            let actual = "";
            for (const p of palabras) {
                if ((actual + " " + p).length * 5 > ancho && actual) { lineas.push(actual); actual = p; } else actual = actual ? `${actual} ${p}` : p;
            }
            return [...lineas, actual];
        }
        text(t) { eventos.textos.push(Array.isArray(t) ? t.join(" ") : String(t)); return this; }
        addImage(...args) { eventos.imagenes.push(args); return this; }
    }
    return { Doc, eventos };
}

const DATOS = {
    respuesta: "Conteo por **organización**: CSIS_Aerospace 214",
    hallazgos: ["CSIS concentra 214 de 479 documentos (45 %)."],
    hallazgos_detalle: [{ texto: "x", soporte: ["CSIS"], doc_ids: ["F2-CSIS-014"] }],
    citations: [{ doc_id: "F2-SWF-120", chunk_id: "F2-SWF-120__chunk_000023", organizacion: "SWF Counterspace", anio: 2026, formato: "pdf", posicion: 23, total_fragmentos: 67 }],
    metadata: { tokens: { total: 3121 }, agentes_invocados: ["orquestador"] },
};
const GRAFICA = { titulo: "Documentos por organización", nota: "Cobertura 34 %", imagen: "data:image/jpeg;base64,AAAA", ancho: 500, alto: 300 };

test("el PDF lleva la consulta, la respuesta, los hallazgos con su doc_id y las fuentes con su chunk_id", () => {
    const { Doc, eventos } = jsPDFSimulado();
    informePdf("Quién publica sobre espacio", DATOS, { graficas: [], jsPDF: Doc });
    const todo = eventos.textos.join("\n");
    assert.match(todo, /Quién publica sobre espacio/);
    assert.match(todo, /Conteo por organización: CSIS_Aerospace 214/, "sin los ** del Markdown");
    assert.match(todo, /CSIS concentra 214/);
    assert.match(todo, /F2-CSIS-014/);
    assert.match(todo, /F2-SWF-120__chunk_000023/);
});

test("las graficas del tablero entran al PDF como imagenes, con su titulo", () => {
    const { Doc, eventos } = jsPDFSimulado();
    informePdf("x", DATOS, { graficas: [GRAFICA, GRAFICA], jsPDF: Doc });
    assert.equal(eventos.imagenes.length, 2);
    assert.equal(eventos.imagenes[0][1], "JPEG");
    assert.ok(eventos.textos.includes("Documentos por organización"));
});

test("cada pagina lleva su pie con la paginacion", () => {
    const { Doc, eventos } = jsPDFSimulado();
    informePdf("x", DATOS, { graficas: [GRAFICA, GRAFICA, GRAFICA, GRAFICA], jsPDF: Doc });
    assert.ok(eventos.paginas > 1, "las graficas no caben en una pagina y pasan a la siguiente");
    for (let n = 1; n <= eventos.paginas; n++) {
        assert.ok(eventos.textos.some((t) => t.includes(`${n} `) && t.includes(`${eventos.paginas}`)), `pie de la pagina ${n}`);
    }
});

test("los caracteres que el PDF no puede dibujar se descartan en vez de salir rotos", () => {
    const { Doc, eventos } = jsPDFSimulado();
    informePdf("→ ¿Qué hay? ✓", { ...DATOS, respuesta: "ok ✓ → fin" }, { jsPDF: Doc });
    const todo = eventos.textos.join("\n");
    assert.ok(!/[→✓]/.test(todo));
    assert.match(todo, /¿Qué hay\?/);
});

test("sin jsPDF cargada avisa claro en vez de fallar mas adelante", () => {
    assert.throws(() => informePdf("x", DATOS, { jsPDF: undefined }), /jsPDF/);
});
