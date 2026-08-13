"""附加模块管理命令 - 外挂 VAE / Text Encoder 的运行时增删查"""
import logging
from typing import Tuple, List
from src.plugin_system import BaseCommand
from ..sd_client import StableDiffusionClient

logger = logging.getLogger("ai_drawing.module_commands")

# 运行时激活的附加模块列表（进程生命周期内持久，重启归零）
_active_modules: List[str] = []


def get_active_modules() -> List[str]:
    """获取当前运行时激活的附加模块列表（供 draw_command / drawing_action 调用）"""
    return list(_active_modules)


class ListModulesCommand(BaseCommand):
    """列出 SD API 可用的附加模块（VAE / Text Encoder）"""

    command_name = "listmodules"
    command_description = "查看 SD WebUI 可用的附加模块（VAE / Text Encoder）列表"
    command_pattern = r"^/listmodules$"

    async def execute(self) -> Tuple[bool, str, bool]:
        try:
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            client = StableDiffusionClient(base_url=api_url)
            modules = await client.get_modules()

            if modules is None:
                await self.send_text(
                    "❌ 获取模块列表失败，请确认 SD WebUI 已启动且支持 /sdapi/v1/sd-modules 端点（需要 SD-Forge）"
                )
                return False, "获取模块列表失败", True

            if not modules:
                await self.send_text("当前没有可用的附加模块。")
                return True, "模块列表为空", True

            lines = ["可用附加模块列表（VAE / Text Encoder）：", ""]
            for m in modules:
                name = m.get("model_name", "")
                marker = " ✓" if name in _active_modules else ""
                lines.append(f"  {name}{marker}")

            if _active_modules:
                lines.append("")
                lines.append(f"当前已激活: {', '.join(_active_modules)}")
            else:
                lines.append("")
                lines.append("当前未激活任何附加模块。")

            lines.append("")
            lines.append("使用 /addmodule <模块名> 激活，/removemodule <模块名> 取消激活。")

            await self.send_text("\n".join(lines))
            return True, "成功获取模块列表", True

        except Exception as e:
            await self.send_text(f"❌ 获取模块列表时出错: {e}")
            return False, f"执行出错: {e}", True


class AddModuleCommand(BaseCommand):
    """激活一个附加模块（VAE / Text Encoder）"""

    command_name = "addmodule"
    command_description = "激活外挂附加模块（VAE / Text Encoder），后续绘图请求将附带该模块"
    command_pattern = r"^/addmodule\s+(?P<name>.+)$"

    async def execute(self) -> Tuple[bool, str, bool]:
        try:
            name = self.matched_groups.get("name", "").strip()
            if not name:
                await self.send_text("请提供模块名称！\n用法: /addmodule <模块名>")
                return False, "缺少模块名称", True

            if name in _active_modules:
                await self.send_text(
                    f"模块 '{name}' 已在激活列表中。\n当前已激活: {', '.join(_active_modules)}"
                )
                return True, "模块已存在", True

            _active_modules.append(name)
            logger.info("激活附加模块: %s，当前列表: %s", name, _active_modules)

            await self.send_text(
                f"✅ 已激活模块: {name}\n当前已激活: {', '.join(_active_modules)}"
            )
            return True, f"已激活模块: {name}", True

        except Exception as e:
            await self.send_text(f"❌ 激活模块时出错: {e}")
            return False, f"执行出错: {e}", True


class RemoveModuleCommand(BaseCommand):
    """取消激活一个附加模块"""

    command_name = "removemodule"
    command_description = "取消激活外挂附加模块（VAE / Text Encoder）"
    command_pattern = r"^/removemodule\s+(?P<name>.+)$"

    async def execute(self) -> Tuple[bool, str, bool]:
        try:
            name = self.matched_groups.get("name", "").strip()
            if not name:
                await self.send_text("请提供模块名称！\n用法: /removemodule <模块名>")
                return False, "缺少模块名称", True

            if name not in _active_modules:
                if _active_modules:
                    await self.send_text(
                        f"模块 '{name}' 不在激活列表中。\n当前已激活: {', '.join(_active_modules)}"
                    )
                else:
                    await self.send_text(f"模块 '{name}' 不在激活列表中。当前激活列表为空。")
                return False, "模块不存在于激活列表", True

            _active_modules.remove(name)
            logger.info("取消激活附加模块: %s，当前列表: %s", name, _active_modules)

            if _active_modules:
                await self.send_text(
                    f"✅ 已取消激活模块: {name}\n当前已激活: {', '.join(_active_modules)}"
                )
            else:
                await self.send_text(f"✅ 已取消激活模块: {name}\n当前激活列表为空。")
            return True, f"已取消激活模块: {name}", True

        except Exception as e:
            await self.send_text(f"❌ 取消激活模块时出错: {e}")
            return False, f"执行出错: {e}", True


class ClearModulesCommand(BaseCommand):
    """清空所有运行时激活的附加模块"""

    command_name = "clearmodules"
    command_description = "清空所有运行时激活的附加模块（VAE / Text Encoder）"
    command_pattern = r"^/clearmodules$"

    async def execute(self) -> Tuple[bool, str, bool]:
        try:
            if not _active_modules:
                await self.send_text("当前激活列表已为空，无需清空。")
                return True, "激活列表已为空", True

            cleared = list(_active_modules)
            _active_modules.clear()
            logger.info("已清空附加模块激活列表，清除的模块: %s", cleared)

            await self.send_text(
                f"✅ 已清空附加模块激活列表。\n已移除: {', '.join(cleared)}"
            )
            return True, "已清空模块激活列表", True

        except Exception as e:
            await self.send_text(f"❌ 清空模块列表时出错: {e}")
            return False, f"执行出错: {e}", True
