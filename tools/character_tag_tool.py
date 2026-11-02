"""通过语义检索返回角色标签，为绘图提示词提供事实来源。"""
import logging
import sqlite3
from typing import Any

from src.plugin_system import BaseTool, ToolParamType

from ..retrieval.service import get_service


logger = logging.getLogger("ai_drawing.character_tag_tool")


class CharacterTagLookupTool(BaseTool):
    name = "character_tag_lookup"
    description = (
        "查询动画、游戏及其他作品角色的 Stable Diffusion 绘图标签，包括精确触发词与核心外观标签。"
        "用户要求绘制明确角色或需要准确角色标签时调用；不确定作品名时可省略并结合多个候选判断。"
    )
    available_for_llm = True
    parameters = [
        ("character_name", ToolParamType.STRING, "要检索的角色名，可以是中文、日文、英文、别名或可能的错字", True, None),
        ("copyright_name", ToolParamType.STRING, "角色所属作品名，可选，用于消歧", False, None),
    ]

    async def execute(self, function_args: dict[str, Any]):
        name = str(function_args.get("character_name") or "").strip()
        copyright_name = str(function_args.get("copyright_name") or "").strip()
        if not name:
            return {"name": self.name, "content": "角色名不能为空。"}
        service = get_service()
        if service is None or not service.enabled:
            return {"name": self.name, "content": "角色标签检索当前不可用，请勿编造角色触发标签。"}
        try:
            rows = await service.search(name, copyright_name)
        except (FileNotFoundError, sqlite3.Error) as error:
            logger.warning("角色标签数据库查询失败（%s）", type(error).__name__)
            return {"name": self.name, "content": "角色标签库当前不可用，请勿编造角色触发标签。"}
        except Exception as error:
            logger.warning("角色标签检索失败（%s）", type(error).__name__)
            return {"name": self.name, "content": "角色标签查询服务暂时不可用，请勿编造角色触发标签。"}
        if not rows:
            return {
                "name": self.name,
                "content": f"标签库未找到与「{name}」匹配的角色。请勿伪造角色触发标签；可询问用户补充作品名。",
            }
        lines = [f"检索到 {len(rows)} 个角色候选；请依据角色名与作品名消歧，不要混合候选的标签。"]
        for row in rows[:3]:
            lines.append(
                f"角色：{row.get('name_cn') or '（无名称）'}；作品：{row.get('copyright_cn') or '（未知）'}\n"
                f"触发标签（原样保留）：{row.get('trigger') or '（库中无触发词）'}\n"
                f"核心外观标签（作为角色特征来源）：{row.get('core_tags') or '（库中无核心标签）'}"
            )
        return {"name": self.name, "content": "\n\n".join(lines)}
