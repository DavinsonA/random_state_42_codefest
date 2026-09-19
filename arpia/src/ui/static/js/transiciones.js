// Pantalla de carga compartida por chat y tablero.
//
// El marcado (#cargador) va en el HTML, visible desde el primer pintado, para
// que la pagina no aparezca a medio armar. Este modulo:
//   - lo desvanece cuando la pagina esta lista (`paginaLista`);
//   - lo vuelve a mostrar al navegar a la otra pagina (`suavizarEnlace`);
//   - lo usa brevemente al rehacer la vista (cambio de idioma: `conTransicion`).
//
// Si el JS falla, una animacion CSS de respaldo lo oculta sola (app.css), asi
// que nunca deja la pagina bloqueada.

const SALIDA_MS = 350;       // igual que la transicion de .cargador en app.css
const ESPERA_FUENTES_MS = 1200;

const cargador = () => document.getElementById("cargador");

function mostrar() {
    const c = cargador();
    if (!c) return;
    c.hidden = false;
    c.classList.remove("cargador--fuera");
    // fuerza el reflow para que la transicion de entrada se vea
    void c.offsetWidth;
    c.classList.add("cargador--visible");
}

function ocultar() {
    const c = cargador();
    if (!c) return;
    c.classList.remove("cargador--visible");
    c.classList.add("cargador--fuera");
    setTimeout(() => {
        if (c.classList.contains("cargador--fuera")) c.hidden = true;
    }, SALIDA_MS);
}

/** Oculta el cargador cuando las fuentes estan listas (con tope, nunca bloquea). */
export async function paginaLista() {
    try {
        await Promise.race([
            document.fonts?.ready ?? Promise.resolve(),
            new Promise((r) => setTimeout(r, ESPERA_FUENTES_MS)),
        ]);
    } catch { /* sin API de fuentes: se oculta igual */ }
    ocultar();
}

/**
 * Al hacer clic en `enlace` (misma pestana), muestra el cargador y navega un
 * instante despues, para que el cambio de pagina se funda en vez de cortar.
 */
export function suavizarEnlace(enlace) {
    if (!enlace || enlace.dataset.suavizado) return;
    enlace.dataset.suavizado = "1";
    enlace.addEventListener("click", (ev) => {
        // Ctrl/Cmd/Shift/clic medio o target=_blank: el navegador abre otra pestana.
        if (ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
        if (enlace.target && enlace.target !== "_self") return;
        ev.preventDefault();
        mostrar();
        setTimeout(() => { window.location.href = enlace.href; }, 180);
    });
}

/** Muestra el cargador mientras se ejecuta `trabajo` (p. ej. rehacer la vista). */
export async function conTransicion(trabajo) {
    mostrar();
    await new Promise((r) => setTimeout(r, 160));
    try {
        await trabajo();
    } finally {
        ocultar();
    }
}

// Al volver con "Atras" el navegador puede restaurar la pagina tal como quedo
// (con el cargador visible): se oculta de nuevo.
window.addEventListener("pageshow", (ev) => {
    if (ev.persisted) ocultar();
});
