"""撤回命令 - /ch"""
import logging
from typing import Tuple

from src.plugin_system import BaseCommand

from ..utils import RecallManager

logger = logging.getLogger("ai_drawing.recall_command")


class RecallCommand(BaseCommand):
    """撤回命令 - /ch（回复目标消息，或撤回本会话最近一张图）"""

    command_name = "ch"
    command_description = "撤回 bot 发送的消息（回复目标消息后使用 /ch）"
    command_pattern = r"^/ch\s*$"

    async def execute(self) -> Tuple[bool, str, bool]:
        try:
            napcat_api_url = self.get_config("recall.napcat_api_url", "http://localhost:3000")
            napcat_api_token = self.get_config("recall.napcat_api_token", "")
            reply_id = RecallManager.extract_reply_id(self)

            if reply_id:
                replied_message = RecallManager.get_message_by_id(reply_id)
                if replied_message and not RecallManager.is_bot_message(replied_message):
                    await self.send_text("只能撤回 bot 发送的消息")
                    return False, "不是 bot 消息", True
                success, msg = await RecallManager.recall_by_message_id(
                    message_id=reply_id,
                    napcat_api_url=napcat_api_url,
                    napcat_api_token=napcat_api_token,
                )
            else:
                chat_id = getattr(self, "chat_id", None) or getattr(
                    getattr(self, "chat_stream", None), "stream_id", None
                )
                if not chat_id:
                    await self.send_text("请回复要撤回的消息后使用 /ch 命令")
                    return False, "未回复消息", True
                success, msg = await RecallManager.recall_latest_image(
                    chat_id=chat_id,
                    napcat_api_url=napcat_api_url,
                    napcat_api_token=napcat_api_token,
                )

            if success:
                await self.send_text("已撤回该消息")
                logger.info("命令触发撤回成功: reply_id=%s", reply_id)
                return True, "撤回成功", True

            await self.send_text(f"撤回失败: {msg}")
            logger.warning("命令触发撤回失败: reply_id=%s, reason=%s", reply_id, msg)
            return False, msg, True
        except Exception as exc:
            logger.error("执行撤回命令时发生异常: %s", exc, exc_info=True)
            await self.send_text(f"撤回失败: {exc}")
            return False, f"执行出错: {exc}", True
