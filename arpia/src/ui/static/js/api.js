// Unica capa del frontend que habla con el backend. Ningun otro archivo hace fetch().
//
// Rutas relativas a proposito: la API y esta interfaz las sirve el mismo
// contenedor (src/api/routing.py), asi que no hay CORS ni URL que configurar.
//
// Cada funcion devuelve JSON ya parseado o lanza ApiError con un mensaje
// legible para mostrar tal cual en la interfaz.

const TIMEOUT_CHAT_MS = 90000;  // el grafo puede tardar; REQUEST_TIMEOUT_S del backend es 60
const TIMEOUT_CORTO_MS = 8000;

export class ApiError extends Error {
    // `codigo` permite a la interfaz mostrar el mensaje en su idioma (i18n.js,
    // claves "error.<codigo>"); `mensaje` queda como texto por defecto.
    constructor(mensaje, { status = 0, causa = null, codigo = "inesperado" } = {}) {
        super(mensaje);
        this.name = "ApiError";
        this.status = status;
        this.causa = causa;
        this.codigo = codigo;
    }
}

async function pedir(ruta, { method = "GET", body, timeoutMs = TIMEOUT_CORTO_MS } = {}) {
    const control = new AbortController();
    const reloj = setTimeout(() => control.abort(), timeoutMs);

    let res;
    try {
        res = await fetch(ruta, {
            method,
            headers: body === undefined ? {} : { "Content-Type": "application/json" },
            body: body === undefined ? undefined : JSON.stringify(body),
            signal: control.signal,
        });
    } catch (err) {
        if (err.name === "AbortError") {
            throw new ApiError("El servicio tardó demasiado en responder. Intenta de nuevo.", { causa: err, codigo: "timeout" });
        }
        throw new ApiError("No se pudo conectar con el servicio.", { causa: err, codigo: "red" });
    } finally {
        clearTimeout(reloj);
    }

    // Un servidor que no es el backend (Live Server, file://) responde HTML, no
    // JSON: la pagina se abrio fuera de A.R.P.I.A. y no hay API detras.
    const tipo = res.headers.get("content-type") || "";
    if (!tipo.includes("json")) {
        throw new ApiError(
            "Esta página no está conectada al backend de A.R.P.I.A. (se abrió desde otro servidor, " +
            "p. ej. Live Server). Con el backend encendido, ábrela en http://localhost:8765/ " +
            "(chat) o http://dashboard.localhost:8765/ (tablero).",
            { status: res.status, codigo: "sin_backend" },
        );
    }

    let datos;
    try {
        datos = await res.json();
    } catch (err) {
        throw new ApiError(`Respuesta ilegible del servicio (HTTP ${res.status}).`, { status: res.status, causa: err, codigo: "ilegible" });
    }

    // /health responde 503 con cuerpo valido cuando nada funciona: se entrega
    // el cuerpo para que la interfaz muestre el estado, no un error generico.
    if (!res.ok && !(ruta === "/health" && datos && datos.status)) {
        throw new ApiError(`El servicio respondió con error (HTTP ${res.status}).`, { status: res.status, codigo: "http" });
    }
    return datos;
}

/** POST /chat — formato ADL: { respuesta, evaluacion, metadata, mode, citations, view_spec }. */
export function enviarChat(texto, sesionId) {
    return pedir("/chat", {
        method: "POST",
        body: { texto, sesion_id: sesionId },
        timeoutMs: TIMEOUT_CHAT_MS,
    });
}

/** GET /health — { status: ok|degraded|down, mode, warnings, ... }. */
export function obtenerSalud() {
    return pedir("/health");
}

/** GET /api/aggregate — datos de una vista del tablero.
 *
 * PROPUESTO, aun no existe en el backend (pedido al arquitecto). Forma esperada:
 *   { filas: [{ grupo, fenomeno, valor, doc_ids: [...] }],
 *     total, cobertura: { con_dato, total }, nota, mode }
 * Lanza ApiError con status 404 mientras no exista.
 */
export function obtenerAgregado({ metrica, group_by, fenomenos, desde, hasta }) {
    const q = new URLSearchParams();
    if (metrica) q.set("metrica", metrica);
    if (group_by) q.set("group_by", group_by);
    if (fenomenos && fenomenos.length) q.set("fenomenos", fenomenos.join(","));
    if (desde) q.set("desde", desde);
    if (hasta) q.set("hasta", hasta);
    return pedir(`/api/aggregate?${q.toString()}`);
}
