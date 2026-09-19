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
    constructor(mensaje, { status = 0, causa = null } = {}) {
        super(mensaje);
        this.name = "ApiError";
        this.status = status;
        this.causa = causa;
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
            throw new ApiError("El servicio tardó demasiado en responder. Intenta de nuevo.", { causa: err });
        }
        throw new ApiError("No se pudo conectar con el servicio.", { causa: err });
    } finally {
        clearTimeout(reloj);
    }

    let datos;
    try {
        datos = await res.json();
    } catch (err) {
        throw new ApiError(`Respuesta ilegible del servicio (HTTP ${res.status}).`, { status: res.status, causa: err });
    }

    // /health responde 503 con cuerpo valido cuando nada funciona: se entrega
    // el cuerpo para que la interfaz muestre el estado, no un error generico.
    if (!res.ok && !(ruta === "/health" && datos && datos.status)) {
        throw new ApiError(`El servicio respondió con error (HTTP ${res.status}).`, { status: res.status });
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

/** GET /api/evidence/{chunk_id} — el fragmento exacto detras de una cita.
 *
 * Responde 200 siempre: `{ disponible: false, motivo }` si no existe.
 */
export function obtenerEvidencia(chunkId) {
    return pedir(`/api/evidence/${encodeURIComponent(chunkId)}`);
}

/** GET /api/document/{doc_id} — el documento reconstruido con fragmentos vecinos.
 *
 * `chunkId` centra la ventana en el fragmento citado y lo marca `citado`;
 * `posicion` es un centro alternativo (para paginar); `ventana` son los
 * fragmentos a cada lado (el backend la limita a 0..10).
 * Devuelve `{ disponible, doc_id, formato, fuente, total_fragmentos, desde, hasta,
 * hay_anterior, hay_siguiente, fragmentos: [{ chunk_id, posicion, texto, truncado,
 * citado }] }`, o `{ disponible: false, motivo }`.
 */
export function obtenerDocumento(docId, { chunkId, posicion, ventana } = {}) {
    const q = new URLSearchParams();
    if (chunkId) q.set("chunk_id", chunkId);
    if (posicion !== undefined && posicion !== null) q.set("posicion", String(posicion));
    if (ventana !== undefined && ventana !== null) q.set("ventana", String(ventana));
    const consulta = q.toString();
    return pedir(`/api/document/${encodeURIComponent(docId)}${consulta ? `?${consulta}` : ""}`);
}

/** GET /api/geo — el corpus no trae lugar; responde `{ disponible: false, motivo, alternativa }`. */
export function obtenerGeo() {
    return pedir("/api/geo");
}

/** GET /api/aggregate — datos de una vista del tablero. Responde 200 siempre.
 *
 * Forma real del backend (src/api/dashboard.py):
 *   { disponible, group_by, metrica, total,
 *     filas: [{ clave, valor, doc_ids: [...] }],
 *     cobertura: { documentos_universo, documentos_en_dimension, documentos_contados,
 *                  sin_dato_en_la_dimension, excluidos_por_fecha } }
 * o `{ disponible: false, motivo }` si el indice no esta. Ninguna fila trae el
 * fenomeno: quien lo necesite pide una vez por fenomeno (`fenomenos`).
 * `viewspec.js` traduce esta forma a la que usan los graficos.
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
