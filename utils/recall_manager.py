"""消息撤回管理器模块"""
import logging
import time
import aiohttp
from typing import Optional, Dict
from src.plugin_system.apis import message_api

logger = logging.getLogger("ai_drawing.recall_manager")


class RecallManager:
    """消息撤回管理器

    负责追踪发送的消息并执行撤回操作。
    由于 MaiBot 内部消息 ID 与 NapCat 平台消息 ID 不同，
    需要通过特定方式获取平台 ID 才能成功撤回。
    """

    # 存储最近发送的消息上下文
    # 格式: {chat_id: {"stream_id": str, "timestamp": float, "message_type": str}}
    _recent_messages: Dict[str, Dict] = {}

    @classmethod
    def track_sent_message(cls, chat_id: str, context: dict) -> None:
        """追踪发送的消息

        Args:
            chat_id: 聊天 ID
            context: 消息上下文，包含 stream_id, timestamp, message_type
        """
        cls._recent_messages[chat_id] = context
        logger.info(f"追踪消息发送: chat_id={chat_id}, context={context}")

    @classmethod
    async def recall_latest_image(
        cls,
        chat_id: str,
        napcat_api_url: str,
    ) -> tuple[bool, str]:
        """撤回最近发送的图片消息

        Args:
            chat_id: 聊天 ID
            napcat_api_url: NapCat API 地址

        Returns:
            (是否成功, 消息)
        """
        # 获取追踪的消息上下文
        context = cls._recent_messages.get(chat_id)
        if not context:
            logger.warning(f"未找到 chat_id={chat_id} 的消息追踪记录")
            return False, "未找到要撤回的消息记录"

        stream_id = context.get("stream_id")
        if not stream_id:
            logger.warning(f"消息上下文中缺少 stream_id: {context}")
            return False, "消息上下文缺少 stream_id"

        # 检查消息是否超过 2 分钟（NapCat 限制）
        timestamp = context.get("timestamp", 0)
        elapsed = time.time() - timestamp
        if elapsed > 120:
            logger.warning(f"消息发送时间过长({elapsed:.1f}秒)，可能无法撤回")
            return False, "消息发送时间过长，无法撤回（仅支持 2 分钟内的消息）"

        # 查询最近发送的消息，获取平台 ID
        try:
            # 查询最近 5 分钟内的消息
            messages = message_api.get_recent_messages(
                stream_id=stream_id,
                hours=0.1,  # 6 分钟
                limit=10
            )

            if not messages:
                logger.warning(f"未查询到 stream_id={stream_id} 的最近消息")
                return False, "未查询到最近的消息"

            # 筛选 bot 发送的图片消息，找到最近的一条
            bot_image_message = None
            for msg in messages:
                # 检查是否是 bot 发送的消息
                if msg.get("sender_type") == "bot" and msg.get("message_type") == "image":
                    bot_image_message = msg
                    break

            if not bot_image_message:
                logger.warning(f"未找到 bot 发送的图片消息: stream_id={stream_id}")
                return False, "未找到 bot 发送的图片消息"

            # 尝试从 additional_config 获取平台消息 ID
            platform_msg_id = bot_image_message.get("additional_config", {}).get("platform_message_id")

            if not platform_msg_id:
                logger.warning(f"消息中未找到 platform_message_id: {bot_image_message.get('message_id')}")
                return False, "无法获取平台消息 ID"

            # 调用 NapCat API 执行撤回
            success = await cls._call_napcat_recall_api(napcat_api_url, platform_msg_id)

            if success:
                # 清除追踪记录
                cls._recent_messages.pop(chat_id, None)
                logger.info(f"成功撤回消息: platform_msg_id={platform_msg_id}")
                return True, "消息已成功撤回"
            else:
                return False, "调用撤回 API 失败"

        except Exception as e:
            logger.error(f"撤回消息时发生异常: {e}", exc_info=True)
            return False, f"撤回失败: {str(e)}"

    @classmethod
    async def recall_by_message_id(
        cls,
        message_id: str,
        napcat_api_url: str,
    ) -> tuple[bool, str]:
        """根据消息 ID 撤回消息

        Args:
            message_id: MaiBot 消息 ID
            napcat_api_url: NapCat API 地址

        Returns:
            (是否成功, 消息)
        """
        try:
            # 通过 message_api 获取消息详情
            message = message_api.get_message_by_id(message_id)

            if not message:
                logger.warning(f"未找到消息: message_id={message_id}")
                return False, "未找到要撤回的消息"

            # 检查消息是否超过 2 分钟
            created_at = message.get("created_at", 0)
            elapsed = time.time() - created_at
            if elapsed > 120:
                logger.warning(f"消息发送时间过长({elapsed:.1f}秒)，可能无法撤回")
                return False, "消息发送时间过长，无法撤回（仅支持 2 分钟内的消息）"

            # 获取平台消息 ID
            platform_msg_id = message.get("additional_config", {}).get("platform_message_id")

            if not platform_msg_id:
                logger.warning(f"消息中未找到 platform_message_id: {message_id}")
                return False, "无法获取平台消息 ID"

            # 调用 NapCat API 执行撤回
            success = await cls._call_napcat_recall_api(napcat_api_url, platform_msg_id)

            if success:
                logger.info(f"成功撤回消息: message_id={message_id}, platform_msg_id={platform_msg_id}")
                return True, "消息已成功撤回"
            else:
                return False, "调用撤回 API 失败"

        except Exception as e:
            logger.error(f"撤回消息时发生异常: {e}", exc_info=True)
            return False, f"撤回失败: {str(e)}"

    @classmethod
    async def _call_napcat_recall_api(cls, api_url: str, platform_msg_id: int) -> bool:
        """调用 NapCat 撤回 API

        Args:
            api_url: NapCat API 地址
            platform_msg_id: 平台消息 ID

        Returns:
            是否成功
        """
        try:
            url = f"{api_url.rstrip('/')}/delete_msg"
            payload = {"message_id": int(platform_msg_id)}

            logger.info(f"调用 NapCat 撤回 API: url={url}, payload={payload}")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        logger.info(f"NapCat API 响应: {result}")

                        # 检查返回状态
                        if result.get("status") == "ok" and result.get("retcode") == 0:
                            return True
                        else:
                            logger.warning(f"NapCat API 返回错误: {result}")
                            return False
                    else:
                        logger.error(f"NapCat API 请求失败: status={resp.status}")
                        return False

        except aiohttp.ClientError as e:
            logger.error(f"NapCat API 网络错误: {e}")
            return False
        except Exception as e:
            logger.error(f"调用 NapCat API 时发生异常: {e}", exc_info=True)
            return False
