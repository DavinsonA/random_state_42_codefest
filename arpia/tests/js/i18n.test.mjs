// Toda clave de idioma que usa la interfaz debe existir en español y en inglés.
//
// Cuando falta una, `t()` devuelve la CLAVE tal cual y esa cadena ("tablero.origen.
// sin_datos") aparece en pantalla como si fuera un texto. Ya paso con la insignia de
// los paneles "Sin datos": el codigo pedia una clave que nadie habia escrito.

import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";

const ESTATICO = new URL("../../src/ui/static/", import.meta.url);

function fuentes(carpeta, extension) {
    return readdirSync(new URL(carpeta, ESTATICO))
        .filter((n) => n.endsWith(extension))
        .map((n) => ({ n, texto: readFileSync(new URL(carpeta + n, ESTATICO), "utf8") }));
}

/** Claves literales: t("clave"), data-i18n="clave" y data-i18n-aria="clave". */
function clavesUsadas() {
    const claves = new Map(); // clave -> archivo donde se usa
    const anadir = (clave, archivo) => claves.has(clave) || claves.set(clave, archivo);
    for (const { n, texto } of fuentes("js/", ".js")) {
        if (n === "i18n.js") continue;
        for (const m of texto.matchAll(/(?<![\w.])t\(\s*["']([\w.]+)["']/g)) anadir(m[1], n);
    }
    for (const { n, texto } of [...fuentes("", ".html")]) {
        for (const m of texto.matchAll(/data-i18n(?:-[\w]+)?="([\w.]+)"/g)) anadir(m[1], n);
    }
    // Familias que el codigo compone con una plantilla (`tablero.origen.${origen}`).
    for (const o of ["corpus", "agente", "simulado", "sin_datos"]) anadir(`tablero.origen.${o}`, "dashboard.js");
    return claves;
}

async function traductor(idioma) {
    globalThis.window = { location: { search: `?lang=${idioma}`, hash: "", href: "http://local/" } };
    globalThis.localStorage = { getItem: () => null, setItem: () => {} };
    globalThis.document = { documentElement: { lang: idioma } };
    // el query hace que Node cargue una instancia nueva con el idioma de este momento
    const { t } = await import(`../../src/ui/static/js/i18n.js?idioma=${idioma}`);
    return t;
}

for (const idioma of ["es", "en"]) {
    test(`toda clave que usa la interfaz existe en ${idioma}`, async () => {
        const t = await traductor(idioma);
        const claves = clavesUsadas();
        assert.ok(claves.size > 40, "no se encontraron claves: la extraccion esta rota");
        const faltan = [...claves].filter(([clave]) => t(clave) === clave).map(([clave, a]) => `${clave} (${a})`);
        assert.deepEqual(faltan, [], `claves sin traducir en ${idioma}`);
    });
}

test("los textos de los paneles sin datos no prometen ejemplos", async () => {
    for (const idioma of ["es", "en"]) {
        const t = await traductor(idioma);
        for (const clave of ["tablero.mapa.sinDatos", "tablero.relaciones.sinDatos"]) {
            assert.doesNotMatch(t(clave), /ejemplo|sample|example/i, `${clave} (${idioma})`);
        }
    }
});
