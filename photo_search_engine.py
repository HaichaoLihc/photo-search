"""Shared SigLIP photo-search engine used by the web API and MCP server."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoProcessor


MODEL_ID = "google/siglip2-base-patch16-384"
BASE_DIR = Path(__file__).parent.resolve()
LOGGER = logging.getLogger(__name__)


def get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def photo_id_for_path(path: str) -> str:
    """Return a stable, opaque ID without exposing a path as the selection key."""
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return f"photo_{digest}"


class PhotoSearchEngine:
    """Lazy-loading wrapper around the existing embeddings and SigLIP model."""

    def __init__(self, base_dir: Path = BASE_DIR) -> None:
        self.base_dir = base_dir.resolve()
        self.device = "cpu"
        self.model: Any = None
        self.processor: Any = None
        self.embeddings: np.ndarray | None = None
        self.paths: list[str] = []
        self._photo_id_to_index: dict[str, int] = {}
        self._lock = threading.RLock()

    @property
    def is_loaded(self) -> bool:
        return self.model is not None and self.processor is not None and self.embeddings is not None

    def load(self) -> None:
        """Load the index and model once. Safe to call repeatedly."""
        with self._lock:
            if self.is_loaded:
                return

            self.device = get_device()
            LOGGER.info("Using computation device: %s", self.device)
            self.reload_index()

            LOGGER.info("Loading model %s", MODEL_ID)
            self.processor = AutoProcessor.from_pretrained(MODEL_ID)
            self.model = AutoModel.from_pretrained(MODEL_ID)
            self.model.eval().to(self.device)
            LOGGER.info("Photo search model is ready")

    def reload_index(self) -> dict[str, Any]:
        """Reload embeddings.npy and paths.json without reloading the model."""
        with self._lock:
            emb_path = self.base_dir / "embeddings.npy"
            paths_path = self.base_dir / "paths.json"
            if not emb_path.exists() or not paths_path.exists():
                raise FileNotFoundError("embeddings.npy or paths.json not found")

            embeddings = np.load(emb_path)
            with paths_path.open("r", encoding="utf-8") as file:
                paths = json.load(file)

            if embeddings.ndim != 2:
                raise ValueError(f"Expected a 2D embedding matrix, got shape {embeddings.shape}")
            if len(paths) != embeddings.shape[0]:
                raise ValueError(
                    f"Index mismatch: {len(paths)} paths for {embeddings.shape[0]} embeddings"
                )

            self.embeddings = embeddings
            self.paths = paths
            self._photo_id_to_index = {
                photo_id_for_path(path): index for index, path in enumerate(paths)
            }
            LOGGER.info("Loaded %d indexed photos with shape %s", len(paths), embeddings.shape)
            return {
                "status": "reloaded",
                "total_images": len(paths),
                "embedding_shape": list(embeddings.shape),
            }

    def stats(self) -> dict[str, Any]:
        dimensions = 0
        if self.embeddings is not None and self.embeddings.ndim == 2:
            dimensions = int(self.embeddings.shape[1])
        return {
            "status": "ready" if self.is_loaded else "not_loaded",
            "total_images": len(self.paths),
            "embedding_dimensions": dimensions,
            "device": self.device,
            "model_id": MODEL_ID,
        }

    def search(self, query: str, count: int, threshold: float = 0.0) -> dict[str, Any]:
        query = query.strip()
        if not query:
            raise ValueError("query must not be empty")
        if count < 1 or count > 200:
            raise ValueError("count must be between 1 and 200")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

        self.load()
        with self._lock:
            if self.embeddings is None or self.model is None or self.processor is None or not self.paths:
                raise RuntimeError("Search index or model is unavailable")

            started = time.perf_counter()
            inputs = self.processor(
                text=[query],
                padding="max_length",
                max_length=64,
                truncation=True,
                return_tensors="pt",
            ).to(self.device)

            with torch.inference_mode():
                query_embedding = self.model.get_text_features(**inputs)
            if hasattr(query_embedding, "pooler_output"):
                query_embedding = query_embedding.pooler_output

            query_embedding = F.normalize(query_embedding, dim=-1)
            query_vector = query_embedding[0].cpu().float().numpy()
            # Apple's Accelerate backend can emit spurious floating-point warnings
            # for a valid float32 matmul, so validate the output explicitly instead.
            with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
                scores = self.embeddings @ query_vector
            if not np.isfinite(scores).all():
                raise RuntimeError("Search produced non-finite similarity scores")
            sorted_indices = np.argsort(scores)[::-1]

            results: list[dict[str, Any]] = []
            for index in sorted_indices:
                score = float(scores[index])
                if score < threshold:
                    break

                path = self.paths[int(index)]
                file_path = Path(path)
                results.append(
                    {
                        "rank": len(results) + 1,
                        "photo_id": photo_id_for_path(path),
                        "index": int(index),
                        "score": round(score, 4),
                        "score_percentage": round(max(0.0, min(1.0, (score + 1) / 2)) * 100, 1),
                        "path": path,
                        "filename": file_path.name,
                        "parent_dir": file_path.parent.name,
                        "exists": file_path.is_file(),
                    }
                )
                if len(results) >= count:
                    break

            return {
                "query": query,
                "total_matches": len(results),
                "total_indexed": len(self.paths),
                "execution_time_ms": round((time.perf_counter() - started) * 1000, 2),
                "results": results,
            }

    def get_photo(self, photo_id: str) -> dict[str, Any]:
        """Resolve a returned opaque photo ID to its indexed file and metadata."""
        if self.embeddings is None or not self.paths:
            self.reload_index()
        with self._lock:
            index = self._photo_id_to_index.get(photo_id)
            if index is None:
                raise KeyError(f"Unknown photo_id: {photo_id}")
            path = self.paths[index]
            file_path = Path(path)
            if not file_path.is_file():
                raise FileNotFoundError(f"Indexed photo is missing: {file_path.name}")
            return {
                "photo_id": photo_id,
                "index": index,
                "path": path,
                "filename": file_path.name,
                "parent_dir": file_path.parent.name,
            }


engine = PhotoSearchEngine()
