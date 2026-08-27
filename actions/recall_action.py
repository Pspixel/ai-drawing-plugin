"""智能撤回 Action 组件"""
import logging
from typing import Tuple

from src.plugin_system import ActionActivationType, BaseAction

from ..utils import RecallManager

logger = logging.getLogger("ai_drawing.recall_action")


class RecallAction(BaseAction):
    """当用户要求撤回 bot 自己发出的消息时执行撤回。"""

    action_name = "recall_image"
    action_description = "撤回机器人自己发送的消息，包括文本、图片等所有类型，不限于图片"
    activation_type = ActionActivationType.ALWAYS  # 改为 ALWAYS，确保始终可用
    activation_keywords = ["撤回", "删了", "删掉", "recall"]
    keyword_case_sensitive = False
    parallel_action = True

    action_parameters = {}
    action_require = [
        "【核心要求】当用户明确要求撤回、删除你刚才发送的消息时使用。范围包括你自己发出的全部消息，不限于图片",
        "【重要】不要在JSON中填写target_message_id参数！系统会自动从用户的回复消息中提取要撤回的目标",
        "【使用方式】只需输出 {\"action\":\"recall_image\"} 即可，不需要任何其他参数",
        "【自动识别】如果用户回复了某条消息说「撤回」，系统会自动撤回被回复的那条消息；如果用户没有回复特定消息，系统会撤回你最近发送的消息",
        "【禁止项】用户没有要求撤回时不要使用；执行此动作后不要再向用户发送「撤回成功」「已撤回」之类的确认提示",
    ]
    associated_types = ["text"]

    async def execute(self) -> Tuple[bool, str]:
        try:
            napcat_api_url = self.get_config("recall.napcat_api_url", "http://localhost:3000")
            napcat_api_token = self.get_config("recall.napcat_api_token", "")

            # 从回复消息中提取要撤回的目标消息ID（用户回复了哪条消息）
            target_message_id = RecallManager.extract_reply_id(self)

            if target_message_id:
                # 如果用户回复了某条消息，撤回被回复的那条消息
                success, msg = await RecallManager.recall_by_message_id(
                    message_id=target_message_id,
                    napcat_api_url=napcat_api_url,
                    napcat_api_token=napcat_api_token,
                )
            else:
                # 如果用户没有回复特定消息，撤回最近发送的消息
                success, msg = await RecallManager.recall_latest_image(
                    chat_id=self.chat_id,
                    napcat_api_url=napcat_api_url,
                    napcat_api_token=napcat_api_token,
                    prefer_image=False,
                )

            if success:
                logger.info("用户触发撤回成功: target_message_id=%s, chat_id=%s", target_message_id, self.chat_id)
                return True, "已撤回目标消息，不要再向用户发送撤回成功之类的提示"

            await self.send_text(f"撤回失败: {msg}")
            logger.warning(
                "用户触发撤回失败: target_message_id=%s, chat_id=%s, reason=%s",
                target_message_id,
                self.chat_id,
                msg,
            )
            return False, msg
        except Exception as exc:
            logger.error("执行撤回操作时发生异常: %s", exc, exc_info=True)
            await self.send_text(f"撤回失败: {exc}")
            return False, f"执行出错: {exc}"
