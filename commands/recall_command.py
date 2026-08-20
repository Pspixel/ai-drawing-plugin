"""撤回命令 - /ch"""
import logging
from typing import Tuple
from src.plugin_system import BaseCommand
from ..utils import RecallManager

logger = logging.getLogger("ai_drawing.recall_command")


class RecallCommand(BaseCommand):
    """撤回命令 - /ch (回复消息时使用)"""

    command_name = "ch"
    command_description = "撤回 bot 发送的消息（需要回复目标消息）"
    command_pattern = r"^/ch\s*$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行撤回命令"""
        try:
            # 检查是否回复了消息
            if not self.reply_to_message_id:
                await self.send_text("请回复要撤回的消息后使用 /ch 命令")
                return False, "未回复消息", True

            # 检查被回复的消息是否是 bot 发送的
            from src.plugin_system.apis import message_api
            replied_message = message_api.get_message_by_id(self.reply_to_message_id)

            if not replied_message:
                await self.send_text("未找到要撤回的消息")
                return False, "消息不存在", True

            if replied_message.get("sender_type") != "bot":
                await self.send_text("只能撤回 bot 发送的消息")
                return False, "不是 bot 消息", True

            # 获取 NapCat API 配置
            napcat_api_url = self.get_config("recall.napcat_api_url", "http://localhost:3000")

            # 执行撤回
            success, msg = await RecallManager.recall_by_message_id(
                message_id=self.reply_to_message_id,
                napcat_api_url=napcat_api_url
            )

            if success:
                await self.send_text("已撤回该消息")
                logger.info(f"命令触发撤回成功: message_id={self.reply_to_message_id}")
                return True, "撤回成功", True
            else:
                await self.send_text(f"撤回失败: {msg}")
                logger.warning(f"命令触发撤回失败: message_id={self.reply_to_message_id}, reason={msg}")
                return False, msg, True

        except Exception as e:
            logger.error(f"执行撤回命令时发生异常: {e}", exc_info=True)
            await self.send_text(f"撤回失败: {str(e)}")
            return False, f"执行出错: {str(e)}", True
