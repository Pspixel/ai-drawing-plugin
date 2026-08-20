"""智能撤回 Action 组件"""
import logging
from typing import Tuple

from src.plugin_system import ActionActivationType, BaseAction

from ..utils import RecallManager

logger = logging.getLogger("ai_drawing.recall_action")


class RecallAction(BaseAction):
    """当用户要求撤回 bot 发出的图片时执行撤回。"""

    action_name = "recall_image"
    action_description = "撤回机器人刚刚发送的图片消息"
    activation_type = ActionActivationType.KEYWORD
    activation_keywords = ["撤回", "删了", "删掉", "recall"]
    keyword_case_sensitive = False
    parallel_action = False

    action_parameters = {}
    action_require = [
        "当用户明确要求撤回、删除刚才由你发送的图片时使用",
        "当用户回复了一张你发送的图片并要求撤回时使用",
        "用户没有要求撤回时不要使用",
    ]
    associated_types = ["text"]

    async def execute(self) -> Tuple[bool, str]:
        try:
            napcat_api_url = self.get_config("recall.napcat_api_url", "http://localhost:3000")
            napcat_api_token = self.get_config("recall.napcat_api_token", "")
            reply_id = RecallManager.extract_reply_id(self)

            if reply_id:
                success, msg = await RecallManager.recall_by_message_id(
                    message_id=reply_id,
                    napcat_api_url=napcat_api_url,
                    napcat_api_token=napcat_api_token,
                )
            else:
                success, msg = await RecallManager.recall_latest_image(
                    chat_id=self.chat_id,
                    napcat_api_url=napcat_api_url,
                    napcat_api_token=napcat_api_token,
                )

            if success:
                await self.send_text("已撤回该消息")
                logger.info("用户触发撤回成功: reply_id=%s, chat_id=%s", reply_id, self.chat_id)
                return True, "撤回成功"

            await self.send_text(f"撤回失败: {msg}")
            logger.warning(
                "用户触发撤回失败: reply_id=%s, chat_id=%s, reason=%s",
                reply_id,
                self.chat_id,
                msg,
            )
            return False, msg
        except Exception as exc:
            logger.error("执行撤回操作时发生异常: %s", exc, exc_info=True)
            await self.send_text(f"撤回失败: {exc}")
            return False, f"执行出错: {exc}"
