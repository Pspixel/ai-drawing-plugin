"""SiliconFlow 异步接口与响应校验。"""
import asyncio
from typing import Any

import aiohttp
import numpy as np


class RetrievalError(Exception):
    """可安全展示的检索服务错误，不包含响应正文或凭据。"""


class SiliconFlowClient:
    def __init__(
        self,
        api_key: str,
        embedding_url: str = "https://api.siliconflow.cn/v1/embeddings",
        embedding_model: str = "Qwen/Qwen3-Embedding-4B",
        timeout: float = 60,
        batch_size: int = 32,
    ):
        self.api_key = api_key
        self.embedding_url = embedding_url
        self.embedding_model = embedding_model
        self.timeout = max(1, float(timeout))
        self.batch_size = max(1, min(128, int(batch_size)))

    async def _post(self, url: str, payload: dict) -> dict[str, Any]:
        if not self.api_key:
            raise RetrievalError("未配置检索服务密钥")
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        raise RetrievalError(f"检索接口返回状态码 {response.status}")
                    result = await response.json()
                    if not isinstance(result, dict):
                        raise RetrievalError("检索接口响应格式异常")
                    return result
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise RetrievalError("检索接口请求失败或超时") from None

    async def embed(self, texts: list[str]) -> np.ndarray:
        """按响应索引还原批次顺序，并检查所有批次维度一致。"""
        batches = []
        dimension = None
        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset:offset + self.batch_size]
            result = await self._post(self.embedding_url, {
                "model": self.embedding_model, "input": batch, "encoding_format": "float",
            })
            matrix = await asyncio.to_thread(self._parse_embeddings, result, len(batch))
            if dimension is not None and matrix.shape[1] != dimension:
                raise RetrievalError("向量批次维度不一致")
            dimension = matrix.shape[1]
            batches.append(matrix)
        if not batches:
            raise RetrievalError("待嵌入文本不能为空")
        return await asyncio.to_thread(np.concatenate, batches, axis=0)

    @staticmethod
    def _parse_embeddings(result: dict, count: int) -> np.ndarray:
        data = result.get("data")
        if not isinstance(data, list) or len(data) != count:
            raise RetrievalError("向量响应数量异常")
        ordered = [None] * count
        for item in data:
            if not isinstance(item, dict):
                raise RetrievalError("向量响应格式异常")
            index = item.get("index")
            vector = item.get("embedding")
            if (type(index) is not int or not 0 <= index < count or ordered[index] is not None
                    or not isinstance(vector, list) or not vector
                    or any(type(value) not in (int, float) for value in vector)):
                raise RetrievalError("向量响应索引或数值异常")
            ordered[index] = vector
        try:
            matrix = np.asarray(ordered, dtype=np.float32)
        except (ValueError, TypeError, OverflowError):
            raise RetrievalError("向量维度或数值异常") from None
        if (matrix.ndim != 2 or not np.isfinite(matrix).all()
                or np.any(np.linalg.norm(matrix, axis=1) == 0)):
            raise RetrievalError("向量包含无效数值")
        return matrix
