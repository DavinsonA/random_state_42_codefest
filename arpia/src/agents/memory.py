"""Memoria de la conversacion: cache semantico y ventana de historial.

Las seis preguntas de AGENTS.md §8:

1. **Proposito.** Evitar volver a pagar por una respuesta que ya se produjo, y
   mantener el historial acotado para que el contexto no crezca sin limite.
2. **Entrada.** La consulta saneada; y, para el historial, la lista de mensajes.
3. **Salida.** Una respuesta previa reutilizable, o nada.
4. **Criterio de exito.** Cero falsos aciertos. Devolver la respuesta de OTRA
   pregunta es peor que no tener cache: cuesta calidad, que pesa el doble que
   eficiencia. De ahi un umbral de 0,95, no de 0,85.
5. **Autoridad.** Lee y escribe su propio almacen en memoria del proceso. No
   llama a modelos ni toca el corpus.
6. **Que NO debe saber.** Nada del contenido de las respuestas que guarda: para
   el son opacas. Solo compara consultas.

**Cero tokens.** El embedding se calcula con el encoder local en la CPU del
contenedor (`src/retrieval/encoder.py`), no en el gateway. Un acierto de cache
ahorra la totalidad de las llamadas de un turno.

**Degradacion:** si el encoder local no esta cargado, el cache no se apaga:
cae a coincidencia exacta sobre el texto normalizado. Menos aciertos, misma
garantia de correccion. El cache NUNCA provoca la carga del modelo: pagar dos
minutos de descarga dentro de la peticion de un evaluador es peor que no tener
cache. La carga se hace al arrancar (`encoder.warmup()`).
"""

from __future__ import annotations

import threading
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from src.api.contracts import AgentResponse, Metadata, Tokens
from src.config import get_logger
from src.observability import tracing
from src.retrieval import encoder

log = get_logger(__name__)

AGENTE = "memoria"

#: Similitud coseno a partir de la cual dos consultas se consideran la misma.
#: Alto a proposito: ver el criterio de exito (4) del docstring.
UMBRAL = 0.95

#: Tope de entradas del cache. Todo almacen lleva tope (AGENTS.md §8): sin el,
#: un proceso de 24 horas acumula vectores hasta quedarse sin memoria.
MAX_ENTRADAS = 256

#: Turnos de conversacion que se conservan. Cada turno son dos mensajes.
VENTANA_TURNOS = 6


def normalizar(texto: str) -> str:
    """Forma canonica para comparar consultas: sin tildes, sin mayusculas, sin
    espacios de sobra y sin signos finales."""
    plano = unicodedata.normalize("NFD", texto.strip().lower())
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return " ".join(plano.split()).rstrip("?!.¿¡")


@dataclass
class Entrada:
    """Una consulta ya respondida."""

    consulta: str
    normalizada: str
    respuesta: AgentResponse
    vector: Any = None


class CacheSemantico:
    """Cache de respuestas por similitud de consulta. Seguro entre hilos."""

    def __init__(self, umbral: float = UMBRAL, max_entradas: int = MAX_ENTRADAS) -> None:
        self.umbral = umbral
        self.max_entradas = max_entradas
        self._entradas: OrderedDict[str, Entrada] = OrderedDict()
        self._lock = threading.Lock()
        self.aciertos = 0
        self.consultas = 0

    # -- consulta --------------------------------------------------------

    def buscar(self, consulta: str) -> AgentResponse | None:
        """Respuesta previa para una consulta equivalente, o None.

        Args:
            consulta: texto ya saneado por el guardian.

        Returns:
            Copia de la respuesta guardada, con la metadata reescrita para
            declarar que este turno no costo ninguna llamada al modelo.
        """
        with tracing.span("tool", "memoria.buscar", input=consulta[:200]) as sp:
            self.consultas += 1
            norma = normalizar(consulta)

            with self._lock:
                exacta = self._entradas.get(norma)
                if exacta is not None:
                    self._entradas.move_to_end(norma)
            if exacta is not None:
                self.aciertos += 1
                sp.set_output("acierto exacto")
                return self._como_acierto(exacta.respuesta, 1.0)

            pareja = self._mas_parecida(consulta)
            if pareja is None:
                sp.set_output("fallo")
                return None

            entrada, similitud = pareja
            if similitud < self.umbral:
                sp.set_output(f"fallo (mejor similitud {similitud:.3f})")
                return None

            self.aciertos += 1
            log.info("acierto de cache semantico (similitud %.3f)", similitud)
            sp.set_output(f"acierto semantico {similitud:.3f}")
            return self._como_acierto(entrada.respuesta, similitud)

    def _mas_parecida(self, consulta: str) -> tuple[Entrada, float] | None:
        """Entrada mas parecida y su similitud coseno. None si no se puede."""
        if not encoder.loaded():
            return None
        with self._lock:
            candidatas = [e for e in self._entradas.values() if e.vector is not None]
        if not candidatas:
            return None
        try:
            import numpy as np

            vector = encoder.encode([consulta])[0]
            matriz = np.vstack([e.vector for e in candidatas])
            # Vectores normalizados: el producto punto ES la similitud coseno.
            similitudes = matriz @ vector
            mejor = int(similitudes.argmax())
            return candidatas[mejor], float(similitudes[mejor])
        except Exception as exc:  # noqa: BLE001 - el cache nunca tumba una consulta
            log.warning("cache semantico no disponible en esta consulta: %s", exc)
            return None

    @staticmethod
    def _como_acierto(respuesta: AgentResponse, similitud: float) -> AgentResponse:
        """Copia la respuesta declarando que este turno no gasto presupuesto.

        La `evaluacion` se conserva intacta —el evaluador mide la calidad de la
        respuesta, y es la misma— pero la `metadata` se reescribe: cero
        llamadas, cero tokens, y el unico agente que intervino fue la memoria.
        Inflar aqui las cifras del turno original seria reportar un consumo que
        no ocurrio.
        """
        copia = respuesta.model_copy(deep=True)
        copia.metadata = Metadata(
            num_interacciones=0,
            agentes_invocados=[AGENTE],
            tokens=Tokens(),
            tokens_por_agente=[],
            latencia_ms=0,  # lo fija el endpoint, de extremo a extremo
            estado=f"cache:{similitud:.2f}",
        )
        return copia

    # -- escritura -------------------------------------------------------

    def guardar(self, consulta: str, respuesta: AgentResponse) -> None:
        """Registra una respuesta. Nunca lanza: un fallo aqui no puede costar
        la consulta que ya se respondio bien."""
        try:
            if respuesta.metadata.estado.startswith("cache"):
                return  # no se re-guarda lo que ya vino del cache
            vector = None
            if encoder.loaded():
                vector = encoder.encode([consulta])[0]
            entrada = Entrada(
                consulta, normalizar(consulta), respuesta.model_copy(deep=True), vector
            )
            with self._lock:
                self._entradas[entrada.normalizada] = entrada
                self._entradas.move_to_end(entrada.normalizada)
                while len(self._entradas) > self.max_entradas:
                    self._entradas.popitem(last=False)  # se descarta la mas antigua
        except Exception as exc:  # noqa: BLE001 - frontera deliberada
            log.warning("no se pudo guardar en el cache: %s", exc)

    # -- operacion -------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        with self._lock:
            entradas = len(self._entradas)
        return {
            "entradas": entradas,
            "consultas": self.consultas,
            "aciertos": self.aciertos,
            "tasa_acierto": round(self.aciertos / self.consultas, 3) if self.consultas else 0.0,
            "semantico": encoder.loaded(),
        }

    def reset(self) -> None:
        with self._lock:
            self._entradas.clear()
        self.aciertos = 0
        self.consultas = 0


#: Instancia del proceso. El cache vive en memoria a proposito: es un acelerador,
#: no una fuente de verdad, y perderlo al reiniciar no rompe nada.
cache = CacheSemantico()


def ventana_historial(mensajes: list[Any], turnos: int = VENTANA_TURNOS) -> list[Any]:
    """Recorta el historial a los ultimos `turnos` intercambios.

    Conserva siempre el primer mensaje si es el de sistema: ahi viven las reglas
    de dominio y de tono, y perderlas por truncado es exactamente el fallo que
    un atacante busca provocar alargando la conversacion.

    Args:
        mensajes: historial completo, del mas antiguo al mas reciente.
        turnos: intercambios a conservar (cada turno son dos mensajes).
    """
    if turnos <= 0 or not mensajes:
        return list(mensajes)

    cabeza: list[Any] = []
    cuerpo = list(mensajes)
    primero = cuerpo[0]
    if getattr(primero, "type", None) == "system" or getattr(primero, "role", None) == "system":
        cabeza = [primero]
        cuerpo = cuerpo[1:]

    limite = turnos * 2
    return cabeza + cuerpo[-limite:] if len(cuerpo) > limite else cabeza + cuerpo
