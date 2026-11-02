"""通用余弦索引与原子缓存，所有方法由调用方放到工作线程执行。"""
import json
import os
import tempfile
import zipfile
from pathlib import Path

import numpy as np

from .client import RetrievalError
from .source import TagRecord


class VectorIndex:
    CACHE_VERSION = 1

    def __init__(self, records: list[TagRecord], vectors: np.ndarray):
        vectors = np.asarray(vectors, dtype=np.float32)
        if (vectors.ndim != 2 or vectors.shape[0] != len(records) or vectors.shape[1] == 0
                or not np.isfinite(vectors).all()):
            raise RetrievalError("索引向量数量、维度或数值异常")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if not np.isfinite(norms).all() or np.any(norms == 0):
            raise RetrievalError("索引包含无效向量")
        self.records = records
        self.vectors = vectors / norms

    def search(self, query: np.ndarray, limit: int = 30, min_similarity: float = 0.45,
               copyright: str = "") -> list[tuple[TagRecord, float]]:
        query = np.asarray(query, dtype=np.float32)
        if query.shape != (self.vectors.shape[1],) or not np.isfinite(query).all():
            raise RetrievalError("查询向量维度或数值异常")
        norm = np.linalg.norm(query)
        if not np.isfinite(norm) or norm == 0:
            raise RetrievalError("查询向量无效")
        scores = self.vectors @ (query / norm)
        positions = np.argsort(-scores, kind="stable")
        results = []
        for position in positions:
            score = float(scores[position])
            if score < min_similarity or len(results) >= max(0, limit):
                break
            record = self.records[position]
            if copyright and copyright.casefold() not in record.payload.get("copyright_cn", "").casefold():
                continue
            results.append((record, score))
        return results

    @classmethod
    def load(cls, path: Path, records: list[TagRecord], identity: dict):
        try:
            with np.load(path, allow_pickle=False) as cached:
                metadata = json.loads(str(cached["metadata"].item()))
                if metadata != {"version": cls.CACHE_VERSION, **identity}:
                    return None
                return cls(records, cached["vectors"])
        except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile, RetrievalError):
            return None

    def save(self, path: Path, identity: dict) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                np.savez(stream, vectors=self.vectors, metadata=json.dumps(
                    {"version": self.CACHE_VERSION, **identity}, ensure_ascii=False, sort_keys=True,
                ))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
