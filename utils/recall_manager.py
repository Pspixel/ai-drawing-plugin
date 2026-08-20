"""消息撤回管理器模块"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from src.config.config import global_config
from src.plugin_system.apis import message_api

logger = logging.getLogger("ai_drawing.recall_manager")


class RecallManager:
    """追踪已发送消息，并调用 NapCat HTTP API 撤回。

    MaiBot 的 message_api 返回 DatabaseMessages 对象，不是字典。
    NapCat 需要的平台消息 ID 会由适配器 echo 回写到 message_id，
    不会出现在 additional_config.platform_message_id。
    """

    _recent_messages: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _value(obj: Any, name: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @classmethod
    def _is_bot_message(cls, message: Any) -> bool:
        sender_type = cls._value(message, "sender_type")
        if sender_type is not None:
            return sender_type == "bot"
        user_info = cls._value(message, "user_info")
        user_id = cls._value(user_info, "user_id")
        bot_id = getattr(getattr(global_config, "bot", None), "qq_account", None)
        return user_id is not None and bot_id is not None and str(user_id) == str(bot_id)

    @classmethod
    def _is_image_message(cls, message: Any) -> bool:
        message_type = cls._value(message, "message_type")
        if message_type is not None and str(message_type).lower() == "image":
            return True
        if cls._value(message, "is_picid", False):
            return True
        plain_text = str(cls._value(message, "processed_plain_text", "") or "")
        return "[picid:" in plain_text or "[图片" in plain_text

    @classmethod
    def _additional_config(cls, message: Any) -> Dict[str, Any]:
        config = cls._value(message, "additional_config", {})
        if isinstance(config, dict):
            return config
        if isinstance(config, str) and config.strip():
            try:
                parsed = json.loads(config)
                return parsed if isinstance(parsed, dict) else {}
            except (TypeError, json.JSONDecodeError):
                logger.debug("无法解析 additional_config: %r", config)
        return {}

    @classmethod
    def _as_platform_id(cls, value: Any) -> Optional[int]:
        """只接受 echo 回写后的整数平台 ID，忽略 send_api_xxx / m395 这类内部 ID。"""
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.startswith("-"):
            return None
        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _platform_message_id(cls, message: Any, fallback: Any = None) -> Optional[int]:
        config = cls._additional_config(message)
        return (
            cls._as_platform_id(config.get("platform_message_id"))
            or cls._as_platform_id(cls._value(message, "message_id"))
            or cls._as_platform_id(fallback)
        )

    @classmethod
    def _extract_reply_from_seg(cls, seg: Any) -> Optional[str]:
        if seg is None:
            return None
        if isinstance(seg, list):
            for item in seg:
                found = cls._extract_reply_from_seg(item)
                if found:
                    return found
            return None
        seg_type = cls._value(seg, "type")
        data = cls._value(seg, "data")
        if seg_type == "reply" and data not in (None, ""):
            if isinstance(data, dict):
                return str(
                    data.get("id")
                    or data.get("message_id")
                    or data.get("data")
                    or ""
                ) or None
            return str(data)
        if seg_type == "seglist":
            return cls._extract_reply_from_seg(data)
        return None

    @classmethod
    def extract_reply_id(cls, source: Any) -> Optional[str]:
        """从 Action/Command 实例或消息对象中取出被回复消息 ID。"""
        if source is None:
            return None

        candidates = [
            source,
            cls._value(source, "action_message"),
            cls._value(source, "command_message"),
            cls._value(source, "message"),
        ]
        seen: List[int] = []
        for item in candidates:
            if item is None:
                continue
            ident = id(item)
            if ident in seen:
                continue
            seen.append(ident)

            for key in ("reply_to", "reply_to_message_id", "reply_message_id"):
                value = cls._value(item, key)
                if value not in (None, ""):
                    return str(value)

            seg_id = cls._extract_reply_from_seg(cls._value(item, "message_segment"))
            if seg_id:
                return seg_id
        return None

    @classmethod
    def get_user_text(cls, source: Any) -> str:
        if source is None:
            return ""
        getter = getattr(source, "get_text", None)
        if callable(getter):
            try:
                text = getter()
                if text:
                    return str(text)
            except Exception:
                logger.debug("get_text() 调用失败", exc_info=True)
        for item in (
            source,
            cls._value(source, "action_message"),
            cls._value(source, "command_message"),
            cls._value(source, "message"),
        ):
            text = cls._value(item, "processed_plain_text") or cls._value(item, "plain_text")
            if text:
                return str(text)
        return ""

    @classmethod
    def get_message_by_id(cls, message_id: str) -> Any:
        getter = getattr(message_api, "get_message_by_id", None)
        if callable(getter):
            return getter(message_id)
        try:
            from src.common.message_repository import find_messages

            messages = find_messages({"message_id": message_id}, limit=1)
            return messages[0] if messages else None
        except Exception:
            logger.exception("查询消息失败: message_id=%s", message_id)
            return None

    @classmethod
    def is_bot_message(cls, message: Any) -> bool:
        return cls._is_bot_message(message)

    @classmethod
    def is_image_message(cls, message: Any) -> bool:
        return cls._is_image_message(message)

    @classmethod
    def track_sent_message(cls, chat_id: str, context: Dict[str, Any]) -> None:
        previous = cls._recent_messages.get(chat_id) or {}
        previous.update(context)
        cls._recent_messages[chat_id] = previous
        logger.info("追踪消息发送: chat_id=%s, context=%s", chat_id, previous)

    @classmethod
    async def capture_sent_image(cls, chat_id: str, stream_id: str, timestamp: float) -> None:
        """发图后等待适配器 echo，把整数平台 ID 写进追踪记录。"""
        await asyncio.sleep(1.2)
        try:
            messages = cls._query_recent_messages(stream_id, timestamp - 5, time.time())
            target = cls._pick_recall_target(messages, timestamp)
            platform_msg_id = cls._platform_message_id(target) if target else None
            raw_id = cls._value(target, "message_id") if target else None
            cls.track_sent_message(
                chat_id,
                {
                    "stream_id": stream_id,
                    "timestamp": timestamp,
                    "message_type": "image",
                    "raw_message_id": raw_id,
                    "platform_message_id": platform_msg_id,
                },
            )
            logger.info(
                "捕获已发图片: chat_id=%s, raw_message_id=%s, platform_message_id=%s",
                chat_id,
                raw_id,
                platform_msg_id,
            )
        except Exception:
            logger.exception("捕获已发图片失败: chat_id=%s", chat_id)

    @classmethod
    def _pick_recall_target(cls, messages: List[Any], timestamp: Optional[float]) -> Any:
        bot_messages = [msg for msg in messages if cls._is_bot_message(msg)]
        image_messages = [msg for msg in bot_messages if cls._is_image_message(msg)]
        # 发出去的图片通常没有 message_type，识别失败时回退到追踪时刻附近的 bot 消息。
        candidates = image_messages or bot_messages
        if timestamp is None:
            return max(candidates, key=lambda msg: cls._value(msg, "time", 0) or 0, default=None)

        window = [
            msg
            for msg in candidates
            if (cls._value(msg, "time", 0) or 0) <= timestamp + 3
        ]
        pool = window or candidates
        # 追踪发生在 send_image 之后、成功提示文本之前，取 time 最接近追踪时刻的那条。
        return min(
            pool,
            key=lambda msg: abs((cls._value(msg, "time", 0) or 0) - timestamp),
            default=None,
        )

    @classmethod
    def _query_recent_messages(cls, chat_id: str, start_time: float, end_time: float) -> List[Any]:
        getter = getattr(message_api, "get_messages_by_time_in_chat", None)
        if callable(getter):
            return getter(
                chat_id=chat_id,
                start_time=start_time,
                end_time=end_time,
                limit=30,
                limit_mode="latest",
                filter_mai=False,
            ) or []
        return message_api.get_recent_messages(
            chat_id=chat_id,
            hours=max((end_time - start_time) / 3600.0, 0.05),
            limit=30,
            filter_mai=False,
        ) or []

    @classmethod
    async def recall_latest_image(
        cls,
        chat_id: str,
        napcat_api_url: str,
        napcat_api_token: str = "",
    ) -> tuple[bool, str]:
        context = cls._recent_messages.get(chat_id) or {}
        query_chat_id = context.get("stream_id") or chat_id
        timestamp = context.get("timestamp")
        now = time.time()
        stored_platform_id = cls._as_platform_id(context.get("platform_message_id"))
        if stored_platform_id:
            logger.info("使用追踪记录中的平台 ID 撤回: %s", stored_platform_id)
            success = await cls._call_napcat_recall_api(
                napcat_api_url, stored_platform_id, napcat_api_token
            )
            if success:
                cls._recent_messages.pop(chat_id, None)
                return True, "消息已成功撤回"
            logger.warning("追踪记录中的平台 ID 撤回失败，改为查询数据库")

        if timestamp and now - timestamp > 120:
            logger.warning("消息发送时间过长(%.1f秒)，无法撤回", now - timestamp)
            return False, "消息发送时间过长，无法撤回（仅支持 2 分钟内的消息）"

        start_time = (timestamp or now) - 15
        end_time = now
        if not timestamp:
            start_time = now - 120

        try:
            messages = cls._query_recent_messages(query_chat_id, start_time, end_time)
            if not messages:
                logger.warning("未查询到 chat_id=%s 的最近消息", query_chat_id)
                return False, "未查询到最近的消息"

            bot_image_message = cls._pick_recall_target(messages, timestamp)
            if not bot_image_message:
                logger.warning("未找到 bot 发送的图片消息: chat_id=%s", query_chat_id)
                return False, "未找到 bot 发送的图片消息"

            additional_config = cls._additional_config(bot_image_message)
            raw_message_id = cls._value(bot_image_message, "message_id")
            platform_msg_id = cls._platform_message_id(bot_image_message)
            logger.info(
                "Bot图片消息详情: message_id=%s, additional_config=%s, platform_msg_id=%s",
                raw_message_id,
                additional_config,
                platform_msg_id,
            )
            if not platform_msg_id:
                return False, f"无法获取平台消息 ID（当前 message_id={raw_message_id}）"

            success = await cls._call_napcat_recall_api(
                napcat_api_url, platform_msg_id, napcat_api_token
            )
            if success:
                cls._recent_messages.pop(chat_id, None)
                logger.info("成功撤回消息: platform_msg_id=%s", platform_msg_id)
                return True, "消息已成功撤回"
            return False, "调用撤回 API 失败"
        except Exception as exc:
            logger.error("撤回消息时发生异常: %s", exc, exc_info=True)
            return False, f"撤回失败: {exc}"

    @classmethod
    async def recall_by_message_id(
        cls,
        message_id: str,
        napcat_api_url: str,
        napcat_api_token: str = "",
    ) -> tuple[bool, str]:
        try:
            message = cls.get_message_by_id(message_id)
            if message:
                created_at = cls._value(message, "created_at") or cls._value(message, "time", 0)
                if created_at and time.time() - created_at > 120:
                    logger.warning("消息发送时间过长，无法撤回: message_id=%s", message_id)
                    return False, "消息发送时间过长，无法撤回（仅支持 2 分钟内的消息）"
                if not cls._is_bot_message(message):
                    return False, "只能撤回 bot 发送的消息"
                platform_msg_id = cls._platform_message_id(message, fallback=message_id)
                logger.info(
                    "消息详情: message_id=%s, additional_config=%s, platform_msg_id=%s",
                    message_id,
                    cls._additional_config(message),
                    platform_msg_id,
                )
            else:
                # 回复段里的 ID 本身常常就是 NapCat 平台 ID。
                platform_msg_id = cls._as_platform_id(message_id)
                logger.info("数据库未找到消息，直接使用平台 ID 撤回: %s", message_id)

            if not platform_msg_id:
                return False, "无法获取平台消息 ID"
            success = await cls._call_napcat_recall_api(
                napcat_api_url, platform_msg_id, napcat_api_token
            )
            if success:
                logger.info("成功撤回消息: message_id=%s, platform_msg_id=%s", message_id, platform_msg_id)
                return True, "消息已成功撤回"
            return False, "调用撤回 API 失败"
        except Exception as exc:
            logger.error("撤回消息时发生异常: %s", exc, exc_info=True)
            return False, f"撤回失败: {exc}"

    @classmethod
    async def _call_napcat_recall_api(
        cls,
        api_url: str,
        platform_msg_id: Any,
        napcat_api_token: str = "",
    ) -> bool:
        try:
            url = f"{api_url.rstrip('/')}/delete_msg"
            payload = {"message_id": int(platform_msg_id)}
            headers = {}
            if napcat_api_token and napcat_api_token.strip():
                headers["Authorization"] = f"Bearer {napcat_api_token.strip()}"
            logger.info("调用 NapCat 撤回 API: url=%s, payload=%s", url, payload)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    body = await response.text()
                    if response.status != 200:
                        logger.error("NapCat API 请求失败: status=%s, body=%s", response.status, body)
                        return False
                    try:
                        result = json.loads(body) if body else {}
                    except json.JSONDecodeError:
                        logger.error("NapCat API 返回非 JSON: %s", body)
                        return False
                    logger.info("NapCat API 响应: %s", result)
                    return result.get("status") == "ok" and result.get("retcode") == 0
        except aiohttp.ClientError as exc:
            logger.error("NapCat API 网络错误: %s", exc)
            return False
        except (TypeError, ValueError) as exc:
            logger.error("平台消息 ID 无法转为整数 %r: %s", platform_msg_id, exc)
            return False
        except Exception as exc:
            logger.error("调用 NapCat API 时发生异常: %s", exc, exc_info=True)
            return False
