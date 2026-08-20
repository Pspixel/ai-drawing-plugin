"""智能撤回 Action 组件"""
import logging
from typing import Tuple
from src.plugin_system import BaseAction, ActionActivationType
from ..utils import RecallManager

logger = logging.getLogger("ai_drawing.recall_action")


class RecallAction(BaseAction):
    """智能撤回 Action - 当用户回复特定消息时，bot 自动撤回该消息"""

    activation_type = ActionActivationType.REPLY

    def match(self) -> bool:
        """匹配规则：用户回复 bot 发送的图片消息"""
        # 检查是否是回复消息
        if not self.reply_to_message_id:
            return False

        # 检查被回复的消息是否是 bot 发送的
        from src.plugin_system.apis import message_api
        replied_message = message_api.get_message_by_id(self.reply_to_message_id)

        if not replied_message:
            return False

        # 检查是否是 bot 发送的图片消息
        if replied_message.get("sender_type") != "bot":
            return False

        if replied_message.get("message_type") != "image":
            return False

        # 检查用户消息内容是否包含撤回关键词
        user_text = self.get_text().strip().lower()
        recall_keywords = ["撤回", "撤", "删除", "删了", "recall"]

        return any(keyword in user_text for keyword in recall_keywords)

    async def execute(self) -> Tuple[bool, str]:
        """执行撤回操作"""
        try:
            # 获取 NapCat API 配置
            napcat_api_url = self.get_config("recall.napcat_api_url", "http://localhost:3000")

            # 执行撤回
            success, msg = await RecallManager.recall_by_message_id(
                message_id=self.reply_to_message_id,
                napcat_api_url=napcat_api_url
            )

            if success:
                await self.send_text("已撤回该消息")
                logger.info(f"用户触发撤回成功: message_id={self.reply_to_message_id}")
                return True, "撤回成功"
            else:
                await self.send_text(f"撤回失败: {msg}")
                logger.warning(f"用户触发撤回失败: message_id={self.reply_to_message_id}, reason={msg}")
                return False, msg

        except Exception as e:
            logger.error(f"执行撤回操作时发生异常: {e}", exc_info=True)
            await self.send_text(f"撤回失败: {str(e)}")
            return False, f"执行出错: {str(e)}"
