// Progreso en vivo del turno, para el asistente del tablero: un cronometro real y los pasos que
// el backend ya reporto (GET /api/progress), los mismos que muestra el modulo de chat.
//
// Todo aqui es informativo. Si `/api/progress` falla, tarda o viene vacio, el turno se comporta
// como antes: no hay ningun `throw` que escape y el cronometro corre aparte de la peticion.
// Solo se pintan pasos que el backend reporto: no se estiman porcentajes ni se anuncian agentes
// que todavia no han corrido (una barra de progreso inventada es un dato inventado).

import { obtenerProgreso } from "./api.js";

//: Cada cuanto se pregunta por el progreso.
const MS_PROGRESO = 700;

// Nombres de span -> lo que lee un analista. Lo que no este aqui se muestra tal cual: un paso
// nuevo aparece con su nombre tecnico, feo pero honesto.
export const ETIQUETAS_PASO = {
    "guardian.revisar_entrada": "Revisando la consulta",
    "guardian.revisar_salida": "Revisando la respuesta",
    "memoria.buscar": "Consultando memoria",
    "orquestador.planificar": "Decidiendo a qué agentes delegar",
    "ejecutar.agente_documental": "Agente documental",
    "ejecutar.agente_visualizador": "Agente visualizador",
    "ejecutar.agente_analitico": "Agente analítico",
    "documental.redactar": "Redactando el análisis",
    "visualizador.emitir": "Eligiendo la vista del tablero",
    "verificador.corregir": "Verificando contra la evidencia",
    buscar_corpus: "Buscando en el corpus",
    detalle_documento: "Leyendo un documento",
    consultar_agregado: "Contando sobre la metadata",
    componentes_disponibles: "Consultando el catálogo de vistas",
    emitir_view_spec: "Definiendo la vista",
    delegar_documental: "Delegando al documental",
    delegar_visualizacion: "Delegando al visualizador",
    delegar_analitico: "Delegando al analítico",
};

export const etiquetaDePaso = (nombre) => ETIQUETAS_PASO[nombre] || nombre;

function nodo(etiqueta, clase, texto) {
    const n = document.createElement(etiqueta);
    if (clase) n.className = clase;
    if (texto !== undefined) n.textContent = String(texto);
    return n;
}

/** Una fila de paso: el agente o la herramienta y lo que tardo. */
export function filaDePaso(nombre, duracionMs) {
    const fila = nodo("li", "progreso-paso");
    fila.append(nodo("span", "chip-agente", etiquetaDePaso(nombre)));
    fila.append(nodo("span", "progreso-ms mono", `${Math.round(duracionMs)} ms`));
    return fila;
}

/**
 * Monta el cronometro y la lista de pasos dentro de `contenedor` y sigue el turno.
 *
 * Devuelve `{ detener, finalizar }`. `detener()` para el sondeo (idempotente, sin red) y devuelve
 * los pasos vistos; `finalizar()` hace una ultima consulta antes, para no perder los pasos que
 * ocurrieron entre el ultimo sondeo y la respuesta.
 */
export function seguirProgreso(contenedor, sesionId) {
    const progreso = nodo("div", "progreso");
    const reloj = nodo("span", "progreso-reloj mono", "0,0 s");
    const lista = nodo("ul", "progreso-pasos");
    // El lector de pantalla anuncia cada paso nuevo sin robar el foco.
    lista.setAttribute("aria-live", "polite");
    progreso.append(reloj, lista);
    contenedor.append(progreso);

    const inicio = Date.now();
    const vistos = new Set();
    const pasos = [];
    let vivo = true;
    let enVuelo = false;

    const relojId = setInterval(() => {
        if (vivo) reloj.textContent = `${((Date.now() - inicio) / 1000).toFixed(1).replace(".", ",")} s`;
    }, 100);

    async function consultar() {
        // Sin solapar peticiones: si una tarda mas que el intervalo, se espera.
        if (enVuelo) return;
        enVuelo = true;
        try {
            const datos = await obtenerProgreso(sesionId);
            if (!datos || !datos.disponible) return;
            for (const paso of datos.pasos || []) {
                if (vistos.has(paso.span_id)) continue;
                vistos.add(paso.span_id);
                pasos.push({ nombre: paso.nombre, duracion_ms: Number(paso.duracion_ms) || 0 });
                lista.append(filaDePaso(paso.nombre, paso.duracion_ms));
            }
        } catch {
            // Silencio deliberado: un fallo del adorno no se le cuenta al usuario, que espera
            // una respuesta que sigue en camino.
        } finally {
            enVuelo = false;
        }
    }

    const consultaId = setInterval(() => {
        if (vivo) consultar();
    }, MS_PROGRESO);
    consultar();

    function detener() {
        vivo = false;
        clearInterval(relojId);
        clearInterval(consultaId);
        return pasos;
    }

    return {
        detener,
        async finalizar() {
            if (vivo) await consultar();
            return detener();
        },
    };
}
