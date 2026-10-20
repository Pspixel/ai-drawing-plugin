"""角色标签查询命令 - /chartag"""
import asyncio
import logging
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from src.config.config import global_config
from src.plugin_system import BaseCommand, ReplyContentType

from ..utils.character_tag_db import (
    DEFAULT_DB_PATH,
    DEFAULT_THUMBS_DIR,
    load_thumbnail_base64,
    parse_query,
    search_characters,
)

logger = logging.getLogger("ai_drawing.character_tag_command")

# 单次查询默认最多返回的角色数（合并转发中的每张图片都可能触发一次识图，故不宜过大）
DEFAULT_MAX_RESULTS = 20
# 合并转发节点要求发送者 ID / 昵称均非空，缺失时使用的兜底值
FALLBACK_SENDER_ID = "10000"
FALLBACK_SENDER_NAME = "AI绘图助手"

USAGE_TEXT = (
    "请提供要查询的角色名！\n"
    "用法: /chartag <角色名> 或 /chartag <角色名>,<作品名>\n"
    "示例: /chartag 甘雨\n"
    "示例: /chartag 甘雨,原神"
)

# (数据库行, 缩略图 base64 或 None)
CharacterItem = Tuple[Dict[str, Any], Optional[str]]


def _clean_field(value: Any) -> str:
    """清理标签字段：去掉首尾空白和结尾多余的逗号，空值显示为（无）"""
    text = str(value or "").strip().rstrip(",").strip()
    return text or "（无）"


def format_character_text(row: Dict[str, Any]) -> str:
    """生成单个角色的信息文本"""
    name_cn = str(row.get("name_cn") or "").strip()
    copyright_cn = str(row.get("copyright_cn") or "").strip()

    title = name_cn
    # 数据库中不少角色名已自带作品名（如“甘雨 (原神)”），此时不再重复追加
    if copyright_cn and not name_cn.endswith((f"({copyright_cn})", f"（{copyright_cn}）")):
        title = f"{name_cn} ({copyright_cn})"

    return (
        f"角色：{title}\n"
        f"触发标签：{_clean_field(row.get('trigger'))}\n"
        f"核心标签：{_clean_field(row.get('core_tags'))}"
    )


def _search_with_thumbnails(
    name: str, copyright_name: Optional[str], limit: int
) -> Tuple[int, List[CharacterItem]]:
    """同步执行数据库查询并读取缩略图（应放在线程中调用，避免阻塞事件循环）"""
    total, rows = search_characters(DEFAULT_DB_PATH, name, copyright_name, limit)
    items: List[CharacterItem] = [
        (row, load_thumbnail_base64(DEFAULT_THUMBS_DIR, row.get("thumbname"))) for row in rows
    ]
    return total, items


def _get_forward_sender() -> Tuple[str, str]:
    """获取合并转发节点的发送者（机器人自身）的 ID 和昵称，均为非空 str"""
    bot_config = global_config.bot
    sender_id = str(getattr(bot_config, "qq_account", "") or "").strip() or FALLBACK_SENDER_ID
    nickname = str(getattr(bot_config, "nickname", "") or "").strip() or FALLBACK_SENDER_NAME
    return sender_id, nickname


class CharacterTagCommand(BaseCommand):
    """角色标签查询命令 - /chartag <角色名>[,<作品名>]"""

    command_name = "chartag"
    command_description = "查询角色的绘图标签（触发标签 / 核心标签 / 缩略图）"
    command_pattern = r"^/(?:chartag|查角色|角色标签)\s+(?P<query>.+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """执行角色标签查询"""
        try:
            if not self.get_config("character_query.enabled", True):
                await self.send_text("角色标签查询功能未启用")
                return False, "功能未启用", True

            # 解析输入
            query = (self.matched_groups.get("query") or "").strip()
            name, copyright_name = parse_query(query)
            if not name:
                await self.send_text(USAGE_TEXT)
                return False, "查询参数无效", True

            max_results = self._get_max_results()

            if self.get_config("character_query.show_searching_tip", True):
                await self.send_text("正在查询，请稍等...")

            # 数据库查询和读图都是同步阻塞操作，放到线程中执行
            try:
                total, items = await asyncio.to_thread(
                    _search_with_thumbnails, name, copyright_name, max_results
                )
            except FileNotFoundError as e:
                logger.error("角色数据库不存在: %s", e)
                await self.send_text("❌ 角色数据库不存在，请检查插件 data/character_tags.db 是否已放置")
                return False, "数据库不存在", True
            except (sqlite3.Error, OSError) as e:
                logger.error("角色数据库查询出错: %s", e, exc_info=True)
                await self.send_text(f"❌ 查询角色数据库时出错: {e}")
                return False, f"数据库查询出错: {e}", True

            if total == 0 or not items:
                await self.send_text("未找到匹配的角色，请换个关键词试试")
                return True, "未找到匹配的角色", True

            if total > len(items):
                await self.send_text(
                    f"找到 {total} 个角色，仅显示前 {len(items)} 个（可用“角色名,作品名”缩小范围）"
                )
            else:
                await self.send_text(f"找到 {total} 个角色")

            # 优先使用合并转发；失败时降级为逐条发送
            if await self._send_as_forward(items):
                return True, f"已以合并转发发送 {len(items)} 个角色", True

            sent, failed = await self._send_one_by_one(items)
            if sent == 0:
                await self.send_text("❌ 角色标签发送失败，请稍后再试")
                return False, "结果发送失败", True
            return True, f"已逐条发送 {sent} 个角色（失败 {failed} 个）", True

        except Exception as e:
            logger.error("执行角色标签查询时发生异常: %s", e, exc_info=True)
            await self.send_text(f"❌ 查询角色标签时出错: {e}")
            return False, f"执行出错: {e}", True

    def _get_max_results(self) -> int:
        """读取并校验 max_results 配置，非法值回退到默认值，最小为 1"""
        raw = self.get_config("character_query.max_results", DEFAULT_MAX_RESULTS)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = DEFAULT_MAX_RESULTS
        return max(1, value)

    async def _send_as_forward(self, items: List[CharacterItem]) -> bool:
        """以合并转发消息发送所有角色，成功返回 True（失败或异常均返回 False 以便降级）"""
        sender_id, nickname = _get_forward_sender()
        nodes = []
        for row, image_b64 in items:
            content: List[Tuple[Any, str]] = []
            if image_b64:
                content.append((ReplyContentType.IMAGE, image_b64))
            content.append((ReplyContentType.TEXT, format_character_text(row)))
            nodes.append((sender_id, nickname, content))

        try:
            # storage_message=False：不把这批内容写入聊天记录
            # （注意：MaiBot 发送前仍会对图片调用识图，这一步无法通过该参数避免）
            ok = await self.send_forward(nodes, storage_message=False)
        except Exception as e:
            logger.warning("合并转发发送异常，降级为逐条发送: %s", e, exc_info=True)
            return False

        if not ok:
            logger.warning("合并转发发送失败，降级为逐条发送")
        return bool(ok)

    async def _send_one_by_one(self, items: List[CharacterItem]) -> Tuple[int, int]:
        """降级方案：逐条发送，返回 (成功数, 失败数)；单条失败不影响其它条目"""
        sent = 0
        failed = 0
        for row, image_b64 in items:
            text = format_character_text(row)
            try:
                if image_b64:
                    ok = await self.send_hybrid(
                        [(ReplyContentType.IMAGE, image_b64), (ReplyContentType.TEXT, text)],
                        storage_message=False,
                    )
                else:
                    ok = await self.send_text(text, storage_message=False)
            except Exception as e:
                logger.warning("逐条发送角色信息失败 (%s): %s", row.get("name_cn"), e)
                ok = False

            if ok:
                sent += 1
            else:
                failed += 1
        return sent, failed
