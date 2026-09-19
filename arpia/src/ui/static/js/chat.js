// Chat del Reto 1: envio de turnos y render de la respuesta ADL.
//
// Todo el texto que viene del backend se inserta con textContent, nunca con
// innerHTML: la respuesta puede contener texto de documentos externos
// (vector de inyeccion, RETO.md §Defensa) y no debe convertirse en marcado.

import { enviarChat, obtenerSalud } from "./api.js";
import { enlazarReferencias, hacerCitaInteractiva } from "./referencias.js";

const INTERVALO_SALUD_MS = 60000;

// Tablero cuando el chat corre en local (localhost / 127.0.0.1).
// null = el tablero de este mismo servidor (dashboard.localhost:<puerto>).
// Pon una URL aqui solo para apuntar a otro servidor de desarrollo.
// En el despliegue no se usa: el tablero es `dashboard.*` del mismo contenedor.
const URL_TABLERO_LOCAL = null;
const CLAVE_SESION = "arpia.sesion_id";

const NOMBRES_AGENTE = {
    orquestador: "Orquestador",
    agente_documental: "Documental",
    agente_visualizador: "Visualizador",
    agente_analitico: "Analítico",
    guardian: "Guardián",
    memoria: "Memoria",
};

const NOMBRES_CHART = {
    timeline: "Serie anual",
    bar: "Barras",
    stacked_bar: "Barras apiladas",
    donut: "Composición",
    table: "Tabla",
    kpi: "Indicador",
};

const NOMBRES_GROUP_BY = {
    fenomeno: "fenómeno",
    organizacion: "organización",
    fuente: "fuente",
    formato: "formato",
    anio: "año",
};

const NOMBRES_METRICA = {
    conteo_documentos: "documentos",
    conteo_fragmentos: "fragmentos",
};

const $ = (id) => document.getElementById(id);

const conversacion = $("conversacion");
const composer = $("composer");
const entrada = $("entrada");
const botonEnviar = $("enviar");

let ocupado = false;

// -- utilidades de DOM -----------------------------------------------------

function el(etiqueta, clase, texto) {
    const nodo = document.createElement(etiqueta);

    if (clase) {
        nodo.className = clase;
    }

    if (texto !== undefined && texto !== null) {
        nodo.textContent = String(texto);
    }

    return nodo;
}

const formatoNumero = new Intl.NumberFormat("es-CO");

function formatoLatencia(ms) {
    if (!Number.isFinite(ms)) {
        return "—";
    }

    return ms < 1000
        ? `${ms} ms`
        : `${(ms / 1000).toLocaleString("es-CO", {
              maximumFractionDigits: 1,
          })} s`;
}

function bajarAlFinal() {
    conversacion.scrollTop = conversacion.scrollHeight;
}

// -- sesion ------------------------------------------------------------------

function nuevoId() {
    if (
        window.crypto &&
        typeof window.crypto.randomUUID === "function"
    ) {
        return window.crypto.randomUUID();
    }

    return `s-${Date.now().toString(36)}-${Math.random()
        .toString(36)
        .slice(2, 10)}`;
}

function sesionId({ renovar = false } = {}) {
    let id = null;

    try {
        id = renovar
            ? null
            : sessionStorage.getItem(CLAVE_SESION);

        if (!id) {
            id = nuevoId();
            sessionStorage.setItem(CLAVE_SESION, id);
        }
    } catch {
        // almacenamiento bloqueado: la sesion vive solo en memoria
        id = id || window.__arpiaSesion || nuevoId();
    }

    window.__arpiaSesion = id;

    return id;
}

// -- texto de la respuesta ---------------------------------------------------
// Render minimo y seguro: parrafos, listas, **negrita** y `codigo`.

function renderInline(padre, texto) {
    const partes = texto.split(
        /(\*\*[^*]+\*\*|`[^`]+`)/
    );

    for (const parte of partes) {
        if (!parte) {
            continue;
        }

        if (
            parte.startsWith("**") &&
            parte.endsWith("**") &&
            parte.length > 4
        ) {
            padre.append(
                el("strong", null, parte.slice(2, -2))
            );
        } else if (
            parte.startsWith("`") &&
            parte.endsWith("`") &&
            parte.length > 2
        ) {
            padre.append(
                el("code", null, parte.slice(1, -1))
            );
        } else {
            padre.append(
                document.createTextNode(parte)
            );
        }
    }
}

function renderTexto(contenedor, texto) {
    const bloques = String(texto || "")
        .trim()
        .split(/\n\s*\n/);

    for (const bloque of bloques) {
        const lineas = bloque
            .split("\n")
            .filter((l) => l.trim());

        if (!lineas.length) {
            continue;
        }

        const vineta = /^\s*[-*•]\s+/;
        const numerada = /^\s*\d+[.)]\s+/;
        const titulo = /^\s*#{1,4}\s+/;

        if (
            lineas.every((l) => vineta.test(l)) ||
            lineas.every((l) => numerada.test(l))
        ) {
            const lista = el(
                lineas.every((l) => vineta.test(l))
                    ? "ul"
                    : "ol"
            );

            for (const l of lineas) {
                const item = el("li");

                renderInline(
                    item,
                    l.replace(vineta, "")
                        .replace(numerada, "")
                );

                lista.append(item);
            }

            contenedor.append(lista);
        } else if (
            lineas.length === 1 &&
            titulo.test(lineas[0])
        ) {
            const h = el(
                "p",
                "texto-subtitulo"
            );

            renderInline(
                h,
                lineas[0].replace(titulo, "")
            );

            contenedor.append(h);
        } else {
            const p = el("p");

            lineas.forEach((l, i) => {
                if (i) {
                    p.append(el("br"));
                }

                renderInline(p, l);
            });

            contenedor.append(p);
        }
    }
}

// -- estado del turno ----------------------------------------------------------

/** Traduce metadata.estado a una etiqueta visible. null = estado normal. */
function describirEstado(estado, mode) {
    const e = String(estado || "ok");

    if (e === "ok") {
        return mode === "stub"
            ? {
                  tono: "advertencia",
                  texto: "Simulado",
              }
            : null;
    }

    if (e === "stub") {
        return {
            tono: "advertencia",
            texto: "Simulado",
        };
    }

    if (
        e === "entrada_vacia" ||
        e === "entrada_no_parseable"
    ) {
        return {
            tono: "info",
            texto: "Sin consulta",
        };
    }

    if (e.startsWith("rechazado")) {
        return {
            tono: "advertencia",
            texto: "Fuera de alcance",
        };
    }

    if (e.startsWith("error_interno")) {
        return {
            tono: "critico",
            texto: "Error interno",
        };
    }

    if (e === "live_no_implementado") {
        return {
            tono: "advertencia",
            texto: "Modo real no habilitado",
        };
    }

    return {
        tono: "info",
        texto: e,
    };
}

// -- piezas de la respuesta ----------------------------------------------------

function renderMeta(metadata) {
    const meta = el("div", "turno-meta");

    const agentes = el("ul", "agentes");
    agentes.setAttribute(
        "aria-label",
        "Agentes invocados"
    );

    for (const id of metadata.agentes_invocados || []) {
        const chip = el(
            "li",
            "chip-agente",
            NOMBRES_AGENTE[id] || id
        );

        chip.title = id;
        agentes.append(chip);
    }

    if (agentes.children.length) {
        meta.append(agentes);
    }

    const tokens = metadata.tokens || {};

    const desglose = (
        metadata.tokens_por_agente || []
    )
        .map(
            (a) =>
                `${a.agente}${
                    a.modelo ? ` (${a.modelo})` : ""
                }: ${formatoNumero.format(
                    a.total || 0
                )}`
        )
        .join("\n");

    const cifras = el("dl", "cifras");

    const cifra = (
        etiqueta,
        valor,
        titulo
    ) => {
        const grupo = el("div", "cifra");

        if (titulo) {
            grupo.title = titulo;
        }

        grupo.append(
            el("dt", null, etiqueta),
            el("dd", null, valor)
        );

        cifras.append(grupo);
    };

    cifra(
        "interacciones",
        formatoNumero.format(
            metadata.num_interacciones || 0
        )
    );

    cifra(
        "tokens",
        formatoNumero.format(
            tokens.total || 0
        ),
        desglose ||
            `entrada ${tokens.input || 0} · salida ${
                tokens.output || 0
            }`
    );

    cifra(
        "latencia",
        formatoLatencia(metadata.latencia_ms)
    );

    meta.append(cifras);

    return meta;
}

function renderCitas(citas) {
    const bloque = el(
        "details",
        "evidencias"
    );

    bloque.open = citas.length <= 3;

    bloque.append(
        el(
            "summary",
            null,
            `Evidencia · ${citas.length} ${
                citas.length === 1
                    ? "fragmento"
                    : "fragmentos"
            }`
        )
    );

    const lista = el(
        "ol",
        "evidencia-lista"
    );

    for (const c of citas) {
        const item = el(
            "li",
            "evidencia"
        );

        const cabeza = el(
            "div",
            "evidencia-id"
        );

        cabeza.append(
            el(
                "span",
                "mono",
                c.doc_id
            ),
            el(
                "span",
                "evidencia-sep",
                "·"
            ),
            el(
                "span",
                "mono evidencia-chunk",
                c.chunk_id
            )
        );

        item.append(cabeza);

        if (c.fuente) {
            item.append(
                el(
                    "p",
                    "evidencia-fuente",
                    c.fuente
                )
            );
        }

        if (c.fragmento) {
            item.append(
                el(
                    "blockquote",
                    "evidencia-texto",
                    c.fragmento
                )
            );
        }

        hacerCitaInteractiva(item, c);

        lista.append(item);
    }

    bloque.append(lista);

    return bloque;
}

// -- enlace al tablero ---------------------------------------------------------

/** Direccion base del tablero segun donde corre el chat.
 *
 * Local: dashboard.localhost del mismo servidor (o URL_TABLERO_LOCAL si se
 * fijo). Desplegado: el mismo contenedor bajo `dashboard.*`
 * (src/api/routing.py elige el HTML por host).
 */
function baseTablero() {
    const { protocol, hostname, port } = window.location;

    if (hostname === "localhost" || hostname === "127.0.0.1") {
        return URL_TABLERO_LOCAL || `${protocol}//dashboard.localhost${port ? `:${port}` : ""}/`;
    }

    if (/^(frontagent|agent)\./.test(hostname)) {
        const host = hostname.replace(/^(frontagent|agent)\./, "dashboard.");
        return `${protocol}//${host}${port ? `:${port}` : ""}/`;
    }

    return null;
}

/** URL del tablero; con `viewSpec` le pasa la vista en el hash. */
function urlTablero(viewSpec) {
    const base = baseTablero();

    if (!base) return null;

    if (viewSpec) {
        return `${base}#vista=${encodeURIComponent(
            JSON.stringify(viewSpec)
        )}`;
    }

    return base;
}

function renderVista(vs) {
    const tarjeta = el(
        "section",
        "vista"
    );

    tarjeta.setAttribute(
        "aria-label",
        "Vista propuesta para el tablero"
    );

    const cabeza = el(
        "div",
        "vista-cabeza"
    );

    cabeza.append(
        el(
            "span",
            "etiqueta",
            "Vista propuesta"
        ),
        el(
            "strong",
            "vista-titulo",
            vs.titulo ||
                NOMBRES_CHART[vs.chart] ||
                vs.chart
        )
    );

    tarjeta.append(cabeza);

    const detalle = el(
        "ul",
        "vista-detalle"
    );

    detalle.append(
        el(
            "li",
            null,
            NOMBRES_CHART[vs.chart] ||
                vs.chart
        )
    );

    detalle.append(
        el(
            "li",
            null,
            `conteo de ${
                NOMBRES_METRICA[
                    vs.metrica
                ] ||
                vs.metrica ||
                "documentos"
            }`
        )
    );

    if (vs.group_by) {
        detalle.append(
            el(
                "li",
                null,
                `por ${
                    NOMBRES_GROUP_BY[
                        vs.group_by
                    ] || vs.group_by
                }`
            )
        );
    }

    const fen =
        vs.fenomenos &&
        vs.fenomenos.length
            ? vs.fenomenos
            : ["F1", "F2", "F3"];

    for (const f of fen) {
        const chip = el(
            "li",
            "fenomeno-chip",
            f
        );

        chip.dataset.fenomeno = f;
        detalle.append(chip);
    }

    if (vs.desde || vs.hasta) {
        detalle.append(
            el(
                "li",
                "mono",
                `${vs.desde || "…"}–${
                    vs.hasta || "…"
                }`
            )
        );
    }

    tarjeta.append(detalle);

    if (vs.nota) {
        const nota = el(
            "p",
            "vista-nota"
        );

        nota.append(
            el(
                "strong",
                null,
                "Nota: "
            ),
            document.createTextNode(
                vs.nota
            )
        );

        tarjeta.append(nota);
    }

    const url = urlTablero(vs);

    if (url) {
        const enlace = el(
            "a",
            "boton boton-secundario",
            "Abrir en el tablero"
        );

        enlace.href = url;
        enlace.target = "_blank";
        enlace.rel = "noopener";

        tarjeta.append(enlace);
    }

    return tarjeta;
}

// -- turnos ------------------------------------------------------------------

function ocultarBienvenida() {
    const b = $("bienvenida");

    if (b) {
        b.hidden = true;
    }
}

function agregarTurnoUsuario(texto) {
    const turno = el(
        "article",
        "turno turno-usuario"
    );

    turno.append(
        el(
            "span",
            "turno-autor",
            "Tú"
        )
    );

    const cuerpo = el(
        "div",
        "turno-texto"
    );

    cuerpo.textContent = texto;

    turno.append(cuerpo);

    conversacion.append(turno);

    bajarAlFinal();
}

function agregarPendiente() {
    const turno = el(
        "article",
        "turno turno-asistente turno-pendiente"
    );

    turno.setAttribute(
        "aria-busy",
        "true"
    );

    turno.append(
        el(
            "span",
            "turno-autor",
            "A.R.P.I.A."
        )
    );

    turno.append(
        el(
            "p",
            "pendiente",
            "Consultando agentes y evidencia del corpus…"
        )
    );

    conversacion.append(turno);

    bajarAlFinal();

    return turno;
}

function renderRespuesta(
    turno,
    datos,
    preguntaOriginal
) {
    turno.classList.remove(
        "turno-pendiente"
    );

    turno.removeAttribute(
        "aria-busy"
    );

    turno.replaceChildren();

    const metadata =
        datos.metadata || {};

    const cabeza = el(
        "div",
        "turno-cabeza"
    );

    cabeza.append(
        el(
            "span",
            "turno-autor",
            "A.R.P.I.A."
        )
    );

    const estado = describirEstado(
        metadata.estado,
        datos.mode
    );

    if (estado) {
        const insignia = el(
            "span",
            `insignia insignia-${estado.tono}`,
            estado.texto
        );

        insignia.title =
            `metadata.estado = ${metadata.estado}`;

        cabeza.append(insignia);
    }

    turno.append(cabeza);

    const cuerpo = el(
        "div",
        "turno-texto"
    );

    renderTexto(
        cuerpo,
        datos.respuesta ||
            "(respuesta vacía)"
    );

    enlazarReferencias(cuerpo, datos.citations);

    turno.append(cuerpo);

    if (datos.view_spec) {
        turno.append(
            renderVista(
                datos.view_spec
            )
        );
    }

    if (
        Array.isArray(datos.citations) &&
        datos.citations.length
    ) {
        turno.append(
            renderCitas(
                datos.citations
            )
        );
    }

    turno.append(
        renderMeta(metadata)
    );

    // "Visualizar esto": puente explicito entre el chat (Reto 1) y el tablero (Reto 2).
    const estadoOk =
        !metadata.estado ||
        metadata.estado === "ok" ||
        metadata.estado === "stub";

    if (
        estadoOk &&
        !datos.view_spec &&
        preguntaOriginal
    ) {
        const acciones = el(
            "div",
            "turno-acciones"
        );

        const visualizar = el(
            "button",
            "boton boton-texto",
            "Visualizar esto"
        );

        visualizar.type = "button";

        visualizar.addEventListener(
            "click",
            () => {
                enviar(
                    `Visualiza en el tablero: ${preguntaOriginal}`
                );
            }
        );

        acciones.append(visualizar);

        turno.append(acciones);
    }
}

function renderFallo(
    turno,
    error,
    texto
) {
    turno.classList.remove(
        "turno-pendiente"
    );

    turno.removeAttribute(
        "aria-busy"
    );

    turno.replaceChildren();

    turno.classList.add(
        "turno-fallo"
    );

    const cabeza = el(
        "div",
        "turno-cabeza"
    );

    cabeza.append(
        el(
            "span",
            "turno-autor",
            "A.R.P.I.A."
        ),
        el(
            "span",
            "insignia insignia-critico",
            "Sin respuesta"
        )
    );

    turno.append(cabeza);

    turno.append(
        el(
            "p",
            "turno-texto",
            error.message ||
                "Ocurrió un error inesperado."
        )
    );

    const acciones = el(
        "div",
        "turno-acciones"
    );

    const reintentar = el(
        "button",
        "boton boton-texto",
        "Reintentar"
    );

    reintentar.type = "button";

    reintentar.addEventListener(
        "click",
        () => {
            turno.remove();

            enviar(texto, {
                repetir: true,
            });
        }
    );

    acciones.append(reintentar);

    turno.append(acciones);
}

// -- envio ------------------------------------------------------------------

async function enviar(
    texto,
    { repetir = false } = {}
) {
    const limpio = String(
        texto || ""
    ).trim();

    if (!limpio || ocupado) {
        return;
    }

    ocupado = true;

    botonEnviar.disabled = true;

    ocultarBienvenida();

    if (!repetir) {
        agregarTurnoUsuario(
            limpio
        );
    }

    const turno =
        agregarPendiente();

    try {
        const datos =
            await enviarChat(
                limpio,
                sesionId()
            );

        renderRespuesta(
            turno,
            datos,
            limpio
        );

        marcarModo(
            datos.mode
        );
    } catch (err) {
        console.error(err);

        renderFallo(
            turno,
            err,
            limpio
        );
    } finally {
        ocupado = false;

        botonEnviar.disabled = false;

        entrada.focus();

        bajarAlFinal();
    }
}

// -- estado del servicio -------------------------------------------------------

function marcarModo(mode) {
    $("aviso-stub").hidden =
        mode !== "stub";
}

async function refrescarSalud() {
    const nodo = $("salud");

    const texto =
        nodo.querySelector(
            ".salud-texto"
        );

    try {
        const salud =
            await obtenerSalud();

        const etiquetas = {
            ok: "Servicio operativo",
            degraded:
                "Servicio degradado",
            down: "Servicio caído",
        };

        nodo.dataset.estado =
            salud.status || "down";

        texto.textContent =
            etiquetas[salud.status] ||
            `Estado: ${salud.status}`;

        nodo.title =
            (salud.warnings || []).join(
                "\n"
            ) ||
            "Sin advertencias";

        marcarModo(
            salud.mode
        );
    } catch (err) {
        nodo.dataset.estado =
            "down";

        texto.textContent =
            "Sin conexión";

        nodo.title =
            err.message;
    }
}

// -- arranque ------------------------------------------------------------------

function ajustarAltura() {
    entrada.style.height =
        "auto";

    entrada.style.height =
        `${Math.min(
            entrada.scrollHeight,
            200
        )}px`;

    entrada.style.overflowY =
        entrada.scrollHeight > 200
            ? "auto"
            : "hidden";
}

composer.addEventListener(
    "submit",
    (ev) => {
        ev.preventDefault();

        const texto =
            entrada.value;

        entrada.value = "";

        ajustarAltura();

        enviar(texto);
    }
);

entrada.addEventListener(
    "keydown",
    (ev) => {
        if (
            ev.key === "Enter" &&
            !ev.shiftKey &&
            !ev.isComposing
        ) {
            ev.preventDefault();

            composer.requestSubmit();
        }
    }
);

entrada.addEventListener(
    "input",
    ajustarAltura
);

$("ejemplos").addEventListener(
    "click",
    (ev) => {
        const boton =
            ev.target.closest(
                ".ejemplo"
            );

        if (boton) {
            enviar(
                boton.textContent
            );
        }
    }
);

$("nueva-conversacion").addEventListener(
    "click",
    () => {
        if (ocupado) {
            return;
        }

        sesionId({
            renovar: true,
        });

        conversacion
            .querySelectorAll(
                ".turno"
            )
            .forEach((t) =>
                t.remove()
            );

        $("bienvenida").hidden =
            false;

        entrada.focus();
    }
);

// -- tablero ------------------------------------------------------------------
// La direccion se configura en URL_TABLERO_LOCAL / baseTablero(), no aqui.

const tablero = urlTablero(null);

if (tablero) {
    const enlace =
        $("enlace-tablero");

    enlace.href = tablero;
    enlace.hidden = false;
}

sesionId();

refrescarSalud();

setInterval(
    refrescarSalud,
    INTERVALO_SALUD_MS
);

entrada.focus();
