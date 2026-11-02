"""规划前获取角色事实，弥补回复工具上下文与 Action 规划的时序差异。"""
import asyncio
import logging
import re
import time
from collections import OrderedDict

from src.config.config import global_config
from src.plugin_system import BaseEventHandler, EventType
from src.plugin_system.apis import database_api, llm_api, tool_api
from src.plugin_system.core.global_announcement_manager import global_announcement_manager
from src.chat.message_receive.chat_stream import get_chat_manager

from ..retrieval.service import get_service
from ..tools.character_tag_tool import CharacterTagLookupTool


logger = logging.getLogger("ai_drawing.character_tag_context")
DRAW_INTENT = re.compile(r"画|绘|生图|出图|生成|来.{0,4}[张幅]|draw|paint|illustrat|generat.{0,15}image", re.IGNORECASE)


class CharacterTagContextHandler(BaseEventHandler):
    event_type = EventType.ON_PLAN
    handler_name = "character_tag_context"
    handler_description = "绘图规划前调用角色标签工具并注入当前会话的事实上下文"
    intercept_message = True
    weight = 10
    # 只缓存最近处理过的消息，避免同一请求在多轮规划中重复检索。
    def __init__(self):
        super().__init__()
        self._processed = OrderedDict()
        self._pending = {}

    async def execute(self, message):
        service = get_service()
        if (message is None or service is None or not service.enabled
                or not global_config.tool.enable_tool
                or not getattr(service, "prefetch_before_plan", True)
                or CharacterTagLookupTool.name in global_announcement_manager.get_disabled_chat_tools(message.stream_id)
                or "ai_drawing" not in (message.llm_prompt or "")
                or not DRAW_INTENT.search(message.plain_text or "")):
            return True, True, None, None, None
        # 以消息原文与发送者去重；有效期仅覆盖最近五分钟的规划循环。
        key = (message.stream_id, message.message_base_info.get("user_id"),
               message.raw_message or message.plain_text)
        now = time.monotonic()
        if now - self._processed.get(key, -600) < 300:
            return True, True, None, None, None
        pending = self._pending.get(key)
        if pending is None:
            pending = asyncio.create_task(self._lookup_and_store(message))
            self._pending[key] = pending
            pending.add_done_callback(lambda task: self._finish_pending(key, task))
        try:
            await asyncio.shield(pending)
            self._processed[key] = time.monotonic()
            self._processed.move_to_end(key)
            while len(self._processed) > 256:
                self._processed.popitem(last=False)
        except Exception as error:
            logger.warning("规划前角色标签查询失败，继续原有绘图流程（%s）", type(error).__name__)
        return True, True, None, None, None

    def _finish_pending(self, key, task):
        if self._pending.get(key) is task:
            self._pending.pop(key, None)
        if not task.cancelled():
            task.exception()

    async def _lookup_and_store(self, message):
        stream = get_chat_manager().get_stream(message.stream_id)
        if stream is None:
            return
        models = llm_api.get_available_models()
        model = models.get("tool_use")
        if model is None:
            return
        success, _, _, _, calls = await llm_api.generate_with_model_with_tools(
            prompt=(
                "识别以下用户绘图请求中的明确命名角色。每个角色调用一次 character_tag_lookup，"
                "只传角色名和已知的作品名，不确定作品名则省略；普通人物、风景和自画像无需调用。"
                "最多查询三个角色。只做工具调用，不生成绘图提示词。\n用户请求：" + message.plain_text
            ),
            model_config=model,
            tool_options=[CharacterTagLookupTool.get_tool_definition()],
            request_type="plugin.character_tag_context",
        )
        if not success or not calls:
            return
        tool = tool_api.get_tool_instance(CharacterTagLookupTool.name, stream)
        if tool is None:
            return
        contents = []
        for call in calls[:3]:
            if call.func_name != CharacterTagLookupTool.name or not isinstance(call.args, dict):
                continue
            result = await tool.execute(call.args)
            if result.get("content"):
                contents.append(str(result["content"]))
        if contents:
            # 此版本规划器会在 ON_PLAN 后重建提示词，所以通过官方动作记录 API 注入事实。
            saved = await database_api.store_action_info(
                chat_stream=stream,
                action_build_into_prompt=True,
                action_prompt_display=(
                    "角色标签查询事实，仅用于以下用户请求：" + message.plain_text + "\n" + "\n\n".join(contents)
                ),
                action_done=True,
                action_data={"request": message.plain_text, "results": contents},
                action_name=CharacterTagLookupTool.name,
            )
            if saved is None:
                raise RuntimeError("角色标签事实上下文保存失败")
