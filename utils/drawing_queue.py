"""绘图任务队列管理器

提供全局单例异步队列，最多同时排队 5 个绘图任务，由后台 worker 串行执行。
Action 组件只需调用 DrawingQueue.enqueue() 即可将任务加入队列并等待结果，
等待期间 asyncio 事件循环不会阻塞，机器人可正常处理其他消息。
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("ai_drawing.drawing_queue")

# 队列最大容量（不含正在执行的任务）
QUEUE_MAX_SIZE = 5


@dataclass
class DrawingTask:
    """单个绘图任务"""
    # txt2img 所需的全部参数
    client_base_url: str
    txt2img_kwargs: Dict[str, Any]
    # 用于将结果回传给调用方
    future: asyncio.Future = field(default_factory=asyncio.Future)


class _DrawingQueue:
    """绘图队列单例（内部类，外部通过 DrawingQueue 访问）"""

    def __init__(self):
        # asyncio.Queue 大小为 0 时不限制，手动控制上限
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._started = False

    def ensure_worker(self):
        """确保后台 worker 正在运行。

        由于 asyncio.Queue 必须在事件循环中使用，首次入队时再启动 worker，
        避免在模块导入时就依赖事件循环。
        """
        if self._started:
            return
        self._started = True
        self._worker_task = asyncio.get_event_loop().create_task(
            self._worker(), name="drawing_queue_worker"
        )
        logger.info("绘图队列 worker 已启动")

    async def _worker(self):
        """后台消费者：串行取出并执行绘图任务"""
        while True:
            task: DrawingTask = await self._queue.get()
            try:
                from ..sd_client import StableDiffusionClient
                client = StableDiffusionClient(base_url=task.client_base_url)
                result = await client.txt2img(**task.txt2img_kwargs)
                if not task.future.done():
                    task.future.set_result(result)
            except Exception as e:
                logger.error("绘图任务执行失败: %s", e)
                if not task.future.done():
                    task.future.set_exception(e)
            finally:
                self._queue.task_done()

    def queue_size(self) -> int:
        """返回当前队列中等待的任务数（不含正在执行的）"""
        return self._queue.qsize()

    async def enqueue(
        self,
        client_base_url: str,
        txt2img_kwargs: Dict[str, Any],
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """将一个绘图任务加入队列并等待结果。

        Args:
            client_base_url: SD WebUI API 基础 URL
            txt2img_kwargs: 传给 StableDiffusionClient.txt2img() 的全部关键字参数

        Returns:
            (是否成功, API 返回的结果字典或 None, 错误信息)
        """
        self.ensure_worker()

        if self._queue.qsize() >= QUEUE_MAX_SIZE:
            return False, None, f"绘图队列已满（最多 {QUEUE_MAX_SIZE} 个），请稍后再试"

        loop = asyncio.get_event_loop()
        task = DrawingTask(
            client_base_url=client_base_url,
            txt2img_kwargs=txt2img_kwargs,
            future=loop.create_future(),
        )
        await self._queue.put(task)
        position = self._queue.qsize()  # 入队后的排队位置（含刚入队的任务）
        logger.info("绘图任务已入队，当前队列长度: %d", position)

        try:
            result = await task.future
            return True, result, ""
        except Exception as e:
            return False, None, str(e)

    def get_position_info(self) -> str:
        """返回队列状态的人类可读描述"""
        size = self._queue.qsize()
        if size == 0:
            return "队列空闲，立即开始绘制"
        return f"前方还有 {size} 个任务在排队"


# 全局单例
DrawingQueue = _DrawingQueue()
