"""Adaptador al indice vectorial construido en la Etapa 1.

Envuelve el artefacto (FAISS + metadata JSONL) detras de una interfaz estable,
para que el resto del sistema no dependa de su formato interno.

**Por que la metadata NO se carga en memoria.** El corpus son 326.866 chunks y
344 MB de JSONL. Cargarlo como lista de dicts cuesta 0,81 GB medidos, que se
suman a 1,3 GB del indice FAISS y a ~2,3 GB del encoder bge-m3: el contenedor
muere antes de responder la primera consulta. En su lugar se recorre el archivo
UNA vez para anotar el desplazamiento de cada linea (2,6 MB de offsets) y cada
fila se lee por `seek` cuando alguien la pide. El coste por consulta es
despreciable —se leen 8 o 10 lineas— y el consumo de memoria deja de depender
del tamano del corpus.

El indice NO se versiona: se monta desde `data/` o desde un volumen (`.env`).
"""

from __future__ import annotations

import json
import re
import threading
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import get_logger
from src.retrieval import encoder
from src.retrieval.enrich import enrich

log = get_logger(__name__)

#: `doc_id` aparece siempre como primera clave de cada linea. Extraerlo con una
#: expresion regular sobre los primeros bytes evita parsear 326.866 JSON
#: completos durante el arranque.
_DOC_ID = re.compile(rb'"doc_id"\s*:\s*"([^"]+)"')


@dataclass(frozen=True)
class Hit:
    """Un fragmento recuperado, con su procedencia."""

    chunk_id: str
    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def citation(self) -> str:
        """Etiqueta corta de procedencia, para mostrar junto a la evidencia."""
        parts = [self.doc_id]
        for key in ("organizacion", "anio", "formato"):
            if self.metadata.get(key):
                parts.append(str(self.metadata[key]))
        return " · ".join(parts)


class VectorIndex:
    """Busqueda densa sobre el indice de la fase clasificatoria.

    La carga es perezosa: importar este modulo no toca disco ni descarga nada.
    Segura para uso concurrente: las lecturas por `seek` van bajo cerrojo,
    porque FastAPI atiende las peticiones sincronas en varios hilos.
    """

    def __init__(self, base_path: str | Path, encoder_name: str | None = None) -> None:
        self.base_path = Path(base_path)
        self.encoder_name = encoder_name
        self._index = None
        self._fh = None
        self._offsets: array[int] = array("q")
        self._doc_offsets: dict[str, int] = {}
        self._doc_chunks: dict[str, int] = {}
        self._manifest: dict[str, Any] = {}
        self._lock = threading.Lock()

    # -- carga -----------------------------------------------------------

    @property
    def meta_path(self) -> Path:
        return self.base_path / "metadata.jsonl"

    @property
    def index_path(self) -> Path:
        return self.base_path / "index.faiss"

    def _scan_offsets(self) -> None:
        """Recorre el JSONL una vez y anota donde empieza cada fila.

        En la misma pasada cuenta fragmentos por documento: es gratis aqui y
        evita un segundo recorrido de 344 MB cuando el agente analitico pide
        `conteo_fragmentos`.
        """
        offsets = array("q")
        docs: dict[str, int] = {}
        chunks: dict[str, int] = {}
        with self.meta_path.open("rb") as fh:
            pos = 0
            for linea in fh:
                if linea.strip():
                    offsets.append(pos)
                    m = _DOC_ID.search(linea, 0, 200)
                    if m:
                        doc_id = m.group(1).decode("utf-8")
                        docs.setdefault(doc_id, pos)
                        chunks[doc_id] = chunks.get(doc_id, 0) + 1
                pos += len(linea)
        self._offsets = offsets
        self._doc_offsets = docs
        self._doc_chunks = chunks

    def _load(self) -> None:
        if self._index is not None:
            return
        import faiss  # import local: pesado, solo cuando se usa

        if not self.index_path.exists():
            raise FileNotFoundError(f"no existe el indice en {self.index_path}")
        if not self.meta_path.exists():
            raise FileNotFoundError(f"no existe la metadata en {self.meta_path}")

        manifest = self.base_path / "manifest.json"
        if manifest.exists():
            self._manifest = json.loads(manifest.read_text("utf-8"))

        self._index = faiss.read_index(str(self.index_path))
        self._scan_offsets()
        self._fh = self.meta_path.open("rb")

        if self._index.ntotal != len(self._offsets):
            raise ValueError(
                f"desalineacion indice<->metadata: {self._index.ntotal} vectores "
                f"vs {len(self._offsets)} filas. No son del mismo build."
            )
        esperadas = self._manifest.get("metadata_rows")
        if esperadas is not None and int(esperadas) != len(self._offsets):
            raise ValueError(
                f"la metadata no coincide con su manifest: {len(self._offsets)} filas "
                f"vs {esperadas} declaradas."
            )
        log.info(
            "indice cargado: %s vectores, %s documentos, metadata por seek",
            self._index.ntotal,
            len(self._doc_offsets),
        )

    def _row_at(self, offset: int) -> dict[str, Any]:
        """Lee y decodifica una fila por su desplazamiento. Bajo cerrojo."""
        with self._lock:
            assert self._fh is not None
            self._fh.seek(offset)
            linea = self._fh.readline()
        return json.loads(linea)

    def row(self, i: int) -> dict[str, Any]:
        """Fila i-esima de la metadata, alineada con el vector i del indice."""
        return self._row_at(self._offsets[i])

    # -- consulta --------------------------------------------------------

    def _encode(self, texts: list[str]):
        """Delega en el encoder compartido: una sola copia del modelo en RAM."""
        return encoder.encode(texts, self.encoder_name or self._manifest.get("model_id"))

    def search(self, query: str, k: int = 10) -> list[Hit]:
        """Recupera los k fragmentos mas similares a la consulta.

        Args:
            query: texto de la consulta, usado literal (no se expande ni traduce).
            k: numero de candidatos a devolver.

        Returns:
            Lista de Hit ordenada por similitud descendente.
        """
        self._load()
        assert self._index is not None

        vector = self._encode([query])
        scores, ids = self._index.search(vector, k)

        hits: list[Hit] = []
        for score, idx in zip(scores[0], ids[0], strict=True):
            if idx < 0:
                continue
            row = enrich(self.row(int(idx)))
            hits.append(
                Hit(
                    chunk_id=row.get("chunk_id", str(idx)),
                    doc_id=row.get("doc_id", ""),
                    text=row.get("texto", row.get("text", "")),
                    score=float(score),
                    metadata=row,
                )
            )
        return hits

    def documents_meta(self, doc_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Metadata del primer fragmento de cada documento pedido.

        Resuelve por diccionario `doc_id -> offset`, sin recorrer el corpus.
        """
        self._load()
        encontrados: dict[str, dict[str, Any]] = {}
        for doc_id in doc_ids:
            offset = self._doc_offsets.get(doc_id)
            if offset is not None:
                encontrados[doc_id] = enrich(self._row_at(offset))
        return encontrados

    def document_table(self) -> list[dict[str, Any]]:
        """Una fila por documento, con sus dimensiones agregables.

        1.826 filas leidas por `seek` desde el primer fragmento de cada
        documento: no recorre el corpus. Es la "tabla estructurada" sobre la que
        opera el agente analitico, y la unica fuente de los conteos del tablero.
        Contar por busqueda semantica daria cifras que parecen correctas y no lo
        son; esto son conteos exactos.
        """
        self._load()
        filas: list[dict[str, Any]] = []
        for doc_id, offset in self._doc_offsets.items():
            row = enrich(self._row_at(offset))
            filas.append(
                {
                    "doc_id": doc_id,
                    "fenomeno": row.get("fenomeno_id", ""),
                    "fenomeno_nombre": row.get("fenomeno_nombre", ""),
                    "organizacion": row.get("organizacion", ""),
                    "formato": row.get("formato", ""),
                    "anio": row.get("anio"),
                    "fuente": row.get("fuente", ""),
                    "n_fragmentos": self._doc_chunks.get(doc_id, 0),
                }
            )
        return filas

    def top_documents(self, hits: list[Hit], n: int = 3) -> list[str]:
        """Agrega fragmentos a documentos por max-pooling de puntaje."""
        best: dict[str, float] = {}
        for hit in hits:
            if hit.score > best.get(hit.doc_id, float("-inf")):
                best[hit.doc_id] = hit.score
        ranked = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
        return [doc_id for doc_id, _ in ranked[:n]]

    # -- estado ----------------------------------------------------------

    def check(self) -> tuple[bool, str | None]:
        """Estado del indice para `/health`. Nunca lanza."""
        try:
            self._load()
            return True, None
        except Exception as exc:  # noqa: BLE001 - frontera deliberada
            return False, f"{type(exc).__name__}: {exc}"

    def stats(self) -> dict[str, Any]:
        """Cifras del indice cargado. Vacio si aun no se ha cargado."""
        if self._index is None:
            return {}
        return {
            "vectores": self._index.ntotal,
            "documentos": len(self._doc_offsets),
            "encoder": self._manifest.get("encoder_name", ""),
        }
