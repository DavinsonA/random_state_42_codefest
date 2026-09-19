"""Guardian: filtro determinista de entrada y salida. CERO tokens.

Las seis preguntas de AGENTS.md §8:

1. **Proposito.** Sanear la consulta del usuario, rechazar los intentos de
   inyeccion de prompt y las peticiones ajenas al dominio, y verificar que la
   respuesta final no filtre configuracion ni instrucciones internas.
2. **Entrada.** El texto crudo del usuario; y, en la revision de salida, el
   texto que el sistema esta a punto de devolver.
3. **Salida.** Un `Veredicto`: permitido o no, el texto saneado y el motivo.
4. **Criterio de exito.** Que ningun ataque de la bateria de ADL obtenga el
   prompt de sistema, un cambio de rol o una respuesta fuera de dominio, **sin**
   rechazar preguntas legitimas sobre los tres fenomenos. Los dos errores
   cuestan: el falso negativo cuesta seguridad (15% del total), el falso
   positivo cuesta calidad (40%).
5. **Autoridad.** Solo lectura y veto. No llama a ningun modelo, no consulta el
   indice, no escribe estado.
6. **Que NO debe saber.** Nada del corpus, del plan del orquestador ni del
   historial. Ve un texto y decide sobre ese texto. Ese aislamiento es lo que
   lo hace auditable.

Por que determinista: la resistencia a inyeccion vale el 15% del puntaje total
del Reto 1 y se mide con ataques sobre el endpoint desplegado. Un filtro basado
en un modelo seria a la vez mas caro y mas atacable — se le puede hablar.
A una expresion regular no.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from src.agents import voz
from src.config import get_logger
from src.observability import tracing

log = get_logger(__name__)

AGENTE = "guardian"

#: Tope de longitud de la consulta. Una entrada enorme es una bomba de tokens
#: y el vehiculo habitual para esconder instrucciones al final del texto.
MAX_CHARS = 4000

Categoria = Literal["ok", "inyeccion", "fuera_de_dominio", "salida_bloqueada"]


@dataclass(frozen=True)
class Veredicto:
    """Resultado de una revision. `texto` es la version saneada de la entrada."""

    permitido: bool
    texto: str
    categoria: Categoria = "ok"
    motivo: str = ""
    patrones: tuple[str, ...] = field(default_factory=tuple)


# -- patrones ---------------------------------------------------------------
# Cada patron lleva nombre para que la traza diga QUE se detecto, no solo que
# algo se bloqueo. Espanol e ingles: los ataques suelen llegar en ingles aunque
# la conversacion sea en espanol.

_INYECCION: tuple[tuple[str, str], ...] = (
    (
        "revelar_instrucciones",
        r"(repite|muestra|dime|imprime|revela|comparte|dame)\b[^.?!]{0,40}\b"
        r"(tus|las|sus)?\s*(instrucciones|reglas|directrices|prompt|system\s*prompt|"
        r"mensaje\s+de\s+sistema)",
    ),
    (
        "revelar_instrucciones_en",
        r"\b(repeat|show|print|reveal|output|tell\s+me)\b[^.?!]{0,40}\b"
        r"(your|the)\s*(instructions|rules|system\s*prompt|prompt|guidelines)",
    ),
    (
        "ignorar_reglas",
        r"\b(ignora|olvida|descarta|omite|salta)\b[^.?!]{0,30}\b"
        r"(lo\s+anterior|las\s+reglas|tus\s+reglas|las\s+instrucciones|tus\s+instrucciones|"
        r"todo\s+lo\s+que)",
    ),
    (
        "ignorar_reglas_en",
        r"\b(ignore|disregard|forget|override)\b[^.?!]{0,30}\b"
        r"(previous|prior|above|all)\b[^.?!]{0,20}\b(instructions?|rules?|prompts?)",
    ),
    (
        "cambio_de_rol",
        r"(a\s+partir\s+de\s+ahora\s+eres|ahora\s+eres|actua\s+como|comportate\s+como|"
        r"haz\s+de\s+cuenta\s+que\s+eres|finge\s+ser|asume\s+el\s+rol)",
    ),
    (
        "cambio_de_rol_en",
        r"\b(you\s+are\s+now|pretend\s+(to\s+be|you)|act\s+as\s+(a|an|if)|"
        r"roleplay\s+as|from\s+now\s+on\s+you)",
    ),
    (
        "modo_sin_restricciones",
        r"\b(modo\s+(desarrollador|dios|libre|sin\s+filtros)|sin\s+(restricciones|filtros|censura)|"
        r"developer\s+mode|jailbreak|\bDAN\b|do\s+anything\s+now|unrestricted\s+mode)",
    ),
    (
        "extraer_configuracion",
        r"\b(variables?\s+de\s+entorno|environment\s+variables?|api[\s_-]?key|"
        r"clave\s+de\s+api|credenciales|credentials|secret[\s_-]?key|tu\s+configuracion|"
        r"archivo\s+\.env|codigo\s+fuente\s+de\s+tu)",
    ),
    (
        "escape_de_etiquetas",
        r"</?\s*(documento_recuperado|system|instrucciones|sistema)\s*>",
    ),
)

#: Peticiones claramente ajenas al dominio. Lista deliberadamente CORTA y
#: literal. La regla no es "rechazar lo que no reconozco" —eso destruiria el
#: bloque de calidad— sino "rechazar lo que es evidentemente otra tarea".
#: Ante la duda, se deja pasar: el agente documental ya declara cuando no tiene
#: evidencia, y esa es una respuesta honesta; un rechazo indebido, no.
_FUERA_DE_DOMINIO: tuple[tuple[str, str], ...] = (
    (
        "pedir_codigo",
        r"\b(escrib\w*|genera\w*|dame|program\w*)\b[^.?!]{0,25}\b(codigo|script|funcion)\b",
    ),
    (
        "pedir_creativo",
        r"\b(escrib\w*|componme|invent\w*)\b[^.?!]{0,20}\b(poema|cuento|chiste|cancion|"
        r"historia\s+de\s+ficcion|guion)\b",
    ),
    ("pedir_receta", r"\breceta\b[^.?!]{0,20}\b(de|para)\b"),
    (
        "pedir_tarea",
        r"\b(haz\w*|resuelve\w*)\b[^.?!]{0,20}\b(mi\s+tarea|este\s+examen|esta\s+ecuacion)\b",
    ),
    (
        "consejo_personal",
        r"\b(consejo|recomendacion)\b[^.?!]{0,25}\b(medico|legal|de\s+salud|"
        r"de\s+inversion|sentimental)\b",
    ),
)

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INVISIBLES = re.compile(r"[​-‏ -‮⁠-⁯﻿]")
_ESPACIOS = re.compile(r"[ \t]{3,}")
_SALTOS = re.compile(r"\n{4,}")

#: Los rechazos salen de `src/agents/voz.py`: una degradacion es cuando mas se
#: nota el tono, y no puede sonar distinta del resto del sistema.
RECHAZO_INYECCION = voz.PETICION_RECHAZADA
RECHAZO_DOMINIO = voz.FUERA_DE_DOMINIO


def _normalizar(texto: str) -> str:
    """Quita disfraces tipograficos antes de buscar patrones.

    Sin este paso, `ignｏra las reglas` (con una o de ancho completo) o un
    caracter de ancho cero entre letras burlan cualquier expresion regular.
    """
    t = unicodedata.normalize("NFKC", texto)
    t = _INVISIBLES.sub("", t)
    t = _CONTROL.sub(" ", t)
    return t


def _sin_acentos(texto: str) -> str:
    """Version sin tildes, solo para comparar contra los patrones."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _coincidencias(texto: str, patrones: tuple[tuple[str, str], ...]) -> tuple[str, ...]:
    plano = _sin_acentos(texto)
    return tuple(nombre for nombre, patron in patrones if re.search(patron, plano, re.IGNORECASE))


def revisar_entrada(texto: str) -> Veredicto:
    """Sanea la consulta y decide si se atiende. No llama a ningun modelo.

    Args:
        texto: lo que escribio el usuario, sin tocar.

    Returns:
        `Veredicto`. Si `permitido` es False, `texto` trae la respuesta de
        rechazo lista para devolver al usuario.
    """
    with tracing.span("tool", "guardian.revisar_entrada", input=texto[:300]) as sp:
        limpio = _normalizar(texto).strip()
        if len(limpio) > MAX_CHARS:
            limpio = limpio[:MAX_CHARS].rsplit(" ", 1)[0] + " […]"
        limpio = _SALTOS.sub("\n\n", _ESPACIOS.sub(" ", limpio))

        inyeccion = _coincidencias(limpio, _INYECCION)
        if inyeccion:
            log.warning("inyeccion detectada: %s", ", ".join(inyeccion))
            sp.set_output(f"bloqueado: {inyeccion}")
            return Veredicto(
                False, RECHAZO_INYECCION, "inyeccion", "patron de inyeccion", inyeccion
            )

        fuera = _coincidencias(limpio, _FUERA_DE_DOMINIO)
        if fuera:
            sp.set_output(f"fuera de dominio: {fuera}")
            return Veredicto(False, RECHAZO_DOMINIO, "fuera_de_dominio", "peticion ajena", fuera)

        sp.set_output("permitido")
        return Veredicto(True, limpio)


def envolver_documento(texto: str, chunk_id: str = "") -> str:
    """Marca contenido recuperado como DATO, nunca como instruccion.

    `RETO.md` §Defensa punto 1 y punto 4: el corpus viene de fuentes externas y
    un documento puede contener texto escrito para que lo obedezca un modelo.
    Es el vector de ataque mas probable en un sistema RAG. La etiqueta de cierre
    se neutraliza dentro del contenido para que no se pueda cerrar el sobre
    antes de tiempo.
    """
    seguro = re.sub(r"</\s*documento_recuperado\s*>", "[/]", texto, flags=re.IGNORECASE)
    atributo = f' id="{chunk_id}"' if chunk_id else ""
    return f"<documento_recuperado{atributo}>\n{seguro}\n</documento_recuperado>"


def revisar_salida(texto: str, secretos: tuple[str, ...] = ()) -> Veredicto:
    """Ultima barrera antes de devolver la respuesta.

    `RETO.md` §Defensa punto 5. Bloquea si la salida contiene un secreto real de
    la configuracion o si reproduce el encabezado del prompt de sistema. No
    intenta adivinar: compara contra valores concretos.
    """
    with tracing.span("tool", "guardian.revisar_salida") as sp:
        for secreto in secretos:
            if secreto and len(secreto) >= 8 and secreto in texto:
                log.error("la salida contenia un secreto de configuracion; bloqueada")
                sp.set_output("bloqueado: secreto en la salida")
                return Veredicto(
                    False, RECHAZO_INYECCION, "salida_bloqueada", "secreto en la salida"
                )

        etiquetas = tuple(par for par in _INYECCION if par[0] == "escape_de_etiquetas")
        filtrado = _coincidencias(texto, etiquetas)
        if filtrado:
            sp.set_output("bloqueado: estructura interna en la salida")
            return Veredicto(
                False, RECHAZO_INYECCION, "salida_bloqueada", "estructura interna expuesta"
            )

        sp.set_output("permitido")
        return Veredicto(True, texto)
