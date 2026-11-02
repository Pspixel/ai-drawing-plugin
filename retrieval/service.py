"""角色检索服务：共用启动任务，索引不可用时降级到 SQLite。"""
import asyncio
import logging
import time
from pathlib import Path

from .client import SiliconFlowClient
from .index import VectorIndex
from .source import DEFAULT_DB_PATH, DEFAULT_INDEX_PATH, load_characters, search_names


logger = logging.getLogger("ai_drawing.tag_retrieval")


class CharacterRetrievalService:
    def __init__(self, client: SiliconFlowClient, db_path: Path = DEFAULT_DB_PATH,
                 index_path: Path = DEFAULT_INDEX_PATH, enabled: bool = True,
                 candidate_count: int = 30, min_similarity: float = 0.45):
        self.client = client
        self.db_path = Path(db_path)
        self.index_path = Path(index_path)
        self.enabled = enabled
        self.candidate_count = max(3, min(100, int(candidate_count)))
        self.min_similarity = max(-1.0, min(1.0, float(min_similarity)))
        self.index = None
        self._build_task = None
        self._retry_after = 0.0

    def start(self):
        """插件注册时安排后台校验；首次查询会等待同一个任务完成。"""
        if not self.enabled or not self.client.api_key:
            return None
        if self._build_task is None and time.monotonic() >= self._retry_after:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return None
            self._build_task = loop.create_task(self._prepare())
        return self._build_task

    async def _prepare(self):
        try:
            records, fingerprint = await asyncio.to_thread(load_characters, self.db_path)
            identity = {
                "fingerprint": fingerprint, "model": self.client.embedding_model,
                "endpoint": self.client.embedding_url,
            }
            index = await asyncio.to_thread(VectorIndex.load, self.index_path, records, identity)
            if index is None and records:
                vectors = await self.client.embed([record.text for record in records])
                index = await asyncio.to_thread(VectorIndex, records, vectors)
                await asyncio.to_thread(index.save, self.index_path, identity)
            self.index = index
            logger.info("角色向量索引就绪，记录数：%d", len(records))
        except Exception as error:
            # 仅记录异常类型，服务响应、密钥和请求头均不进入日志。
            logger.warning("角色向量索引不可用，使用数据库查询（%s）", type(error).__name__)
            self._retry_after = time.monotonic() + 60
        finally:
            self._build_task = None

    async def search(self, name: str, copyright: str = "") -> list[dict[str, str]]:
        name, copyright = name.strip(), (copyright or "").strip()
        if not name:
            raise ValueError("角色名不能为空")
        if not self.enabled:
            return []
        lexical = await asyncio.to_thread(search_names, self.db_path, name, copyright, self.candidate_count)
        if self.index is None:
            task = self.start()
            if task is not None:
                await asyncio.shield(task)
        if self.index is not None and self.client.api_key:
            try:
                query = f"角色：{name}；作品：{copyright}" if copyright else f"角色：{name}"
                vector = await self.client.embed([query])
                vector_candidates = await asyncio.to_thread(
                    self.index.search, vector[0], self.candidate_count, self.min_similarity, copyright,
                )
                return [record.payload.copy() for record, _ in vector_candidates[:3]]
            except Exception as error:
                logger.warning("角色语义查询不可用，使用数据库查询（%s）", type(error).__name__)
        return [record.payload.copy() for record in lexical[:3]]
