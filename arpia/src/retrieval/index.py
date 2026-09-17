"""Adaptador al indice vectorial existente.

Envuelve el artefacto del reto clasificatorio (indice FAISS + metadata JSONL)
detras de una interfaz estable, para que el resto del sistema no dependa de su
formato interno. Si el dia del evento cambia el corpus o el encoder, se cambia
solo este modulo.

El indice NO se versiona en el repositorio: se monta desde `data/` o desde un
volumen. Ver `.env.example`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import get_logger

log = get_logger(__name__)


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
        for key in ("fuente", "pagina", "fecha", "lugar"):
            if self.metadata.get(key):
                parts.append(str(self.metadata[key]))
        return " · ".join(parts)


class VectorIndex:
    """Busqueda densa sobre el indice construido en la fase clasificatoria.

    La carga es perezosa: importar este modulo no toca disco ni GPU.
    """

    def __init__(self, base_path: str | Path, encoder_name: str | None = None) -> None:
        self.base_path = Path(base_path)
        self.encoder_name = encoder_name
        self._index = None
        self._meta: list[dict[str, Any]] | None = None
        self._encoder = None

    # -- carga -----------------------------------------------------------

    def _load(self) -> None:
        if self._index is not None:
            return
        import faiss  # import local: pesado, solo cuando se usa

        index_path = self.base_path / "index.faiss"
        meta_path = self.base_path / "metadata.jsonl"
        if not index_path.exists():
            raise FileNotFoundError(f"no existe el indice en {index_path}")

        self._index = faiss.read_index(str(index_path))
        self._meta = [
            json.loads(line) for line in meta_path.read_text("utf-8").splitlines() if line
        ]

        if self._index.ntotal != len(self._meta):
            raise ValueError(
                f"desalineacion indice<->metadata: {self._index.ntotal} vectores "
                f"vs {len(self._meta)} filas. No son del mismo build."
            )
        log.info("indice cargado: %s vectores", self._index.ntotal)

    def _encode(self, texts: list[str]):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            name = self.encoder_name or "BAAI/bge-m3"
            self._encoder = SentenceTransformer(name, device="cpu")
        return self._encoder.encode(texts, normalize_embeddings=True, convert_to_numpy=True)

    # -- consulta --------------------------------------------------------

    def search(self, query: str, k: int = 10) -> list[Hit]:
        """Recupera los k fragmentos mas similares a la consulta.

        Args:
            query: texto de la consulta, usado literal (no se expande ni traduce).
            k: numero de candidatos a devolver.

        Returns:
            Lista de Hit ordenada por similitud descendente.
        """
        self._load()
        assert self._index is not None and self._meta is not None

        vector = self._encode([query])
        scores, ids = self._index.search(vector, k)

        hits: list[Hit] = []
        for score, idx in zip(scores[0], ids[0], strict=True):
            if idx < 0:
                continue
            row = self._meta[int(idx)]
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

    def top_documents(self, hits: list[Hit], n: int = 3) -> list[str]:
        """Agrega fragmentos a documentos por max-pooling de puntaje."""
        best: dict[str, float] = {}
        for hit in hits:
            if hit.score > best.get(hit.doc_id, float("-inf")):
                best[hit.doc_id] = hit.score
        ranked = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
        return [doc_id for doc_id, _ in ranked[:n]]
