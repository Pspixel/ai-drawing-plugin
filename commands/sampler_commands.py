"""采样器、调度器和放大器管理命令"""
import logging
from typing import Tuple
from src.plugin_system import BaseCommand
from ..sd_client import StableDiffusionClient

logger = logging.getLogger("ai_drawing.sampler_commands")

# 运行时激活的采样器/调度器/放大器（空字符串 = 使用 config 默认值）
_active_sampler: str = ""
_active_scheduler: str = ""
_active_upscaler: str = ""


def get_active_sampler() -> str:
    """获取当前运行时激活的采样器（空字符串表示使用配置默认值）"""
    return _active_sampler


def get_active_scheduler() -> str:
    """获取当前运行时激活的调度器（空字符串表示使用配置默认值）"""
    return _active_scheduler


def get_active_upscaler() -> str:
    """获取当前运行时激活的放大器（空字符串表示使用配置默认值）"""
    return _active_upscaler


class SwitchSamplerCommand(BaseCommand):
    """切换采样器命令 - /sampler [name]"""

    command_name = "sampler"
    command_description = "查看或切换采样器"
    command_pattern = r"^/sampler(?:\s+(?P<sampler_name>.+))?$"

    async def execute(self) -> Tuple[bool, str, bool]:
        global _active_sampler
        try:
            sampler_name = (self.matched_groups.get("sampler_name") or "").strip()
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            client = StableDiffusionClient(base_url=api_url)

            if not sampler_name:
                # 无参数：从 API 拉取列表
                samplers = await client.get_samplers()
                if samplers is None:
                    # 回退到配置列表
                    available = self.get_config("generation.available_samplers", [])
                    if available:
                        lines = ["可用的采样器（来自配置文件）：", ""]
                        for s in available:
                            marker = " ✓（当前）" if s == (_active_sampler or self.get_config("generation.sampler_name", "Euler a")) else ""
                            lines.append(f"  {s}{marker}")
                        lines.append("\n用法: /sampler <采样器名>")
                        await self.send_text("\n".join(lines))
                    else:
                        await self.send_text("❌ 获取采样器列表失败，且配置文件中未设置可用采样器列表")
                    return False, "获取采样器列表失败", True

                current = _active_sampler or self.get_config("generation.sampler_name", "Euler a")
                lines = ["可用的采样器（来自 SD API）：", ""]
                for s in samplers:
                    name = s.get("name", "")
                    marker = " ✓（当前）" if name == current else ""
                    lines.append(f"  {name}{marker}")
                lines.append("\n用法: /sampler <采样器名>")
                await self.send_text("\n".join(lines))
                return True, "显示采样器列表", True

            # 有参数：切换采样器
            _active_sampler = sampler_name
            logger.info("切换采样器: %s", sampler_name)
            await self.send_text(f"✅ 已切换到采样器: {sampler_name}\n下次绘图请求将使用此采样器。")
            return True, f"切换到采样器: {sampler_name}", True

        except Exception as e:
            await self.send_text(f"❌ 切换采样器时出错: {e}")
            return False, f"执行出错: {e}", True


class SwitchSchedulerCommand(BaseCommand):
    """切换调度器命令 - /scheduler [name]"""

    command_name = "scheduler"
    command_description = "查看或切换调度器"
    command_pattern = r"^/scheduler(?:\s+(?P<scheduler_name>.+))?$"

    async def execute(self) -> Tuple[bool, str, bool]:
        global _active_scheduler
        try:
            scheduler_name = (self.matched_groups.get("scheduler_name") or "").strip()
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            client = StableDiffusionClient(base_url=api_url)

            if not scheduler_name:
                # 无参数：从 API 拉取列表
                schedulers = await client.get_schedulers()
                if schedulers is None:
                    available = self.get_config("generation.available_schedulers", [])
                    if available:
                        lines = ["可用的调度器（来自配置文件）：", ""]
                        current = _active_scheduler or self.get_config("generation.scheduler", "")
                        for s in available:
                            marker = " ✓（当前）" if s == current else ""
                            lines.append(f"  {s}{marker}")
                        lines.append("\n用法: /scheduler <调度器名>")
                        await self.send_text("\n".join(lines))
                    else:
                        await self.send_text("❌ 获取调度器列表失败，且配置文件中未设置可用调度器列表")
                    return False, "获取调度器列表失败", True

                current = _active_scheduler or self.get_config("generation.scheduler", "")
                lines = ["可用的调度器（来自 SD API）：", ""]
                for s in schedulers:
                    name = s.get("name", "")
                    label = s.get("label", name)
                    marker = " ✓（当前）" if name == current else ""
                    # 显示 label（显示名），括号内标注传参用的 name（内部名）
                    if label != name:
                        lines.append(f"  {label}（传参名: {name}）{marker}")
                    else:
                        lines.append(f"  {name}{marker}")
                lines.append("\n用法: /scheduler <调度器传参名>（括号内的名称）")
                await self.send_text("\n".join(lines))
                return True, "显示调度器列表", True

            # 有参数：切换调度器
            _active_scheduler = scheduler_name
            logger.info("切换调度器: %s", scheduler_name)
            await self.send_text(f"✅ 已切换到调度器: {scheduler_name}\n下次绘图请求将使用此调度器。")
            return True, f"切换到调度器: {scheduler_name}", True

        except Exception as e:
            await self.send_text(f"❌ 切换调度器时出错: {e}")
            return False, f"执行出错: {e}", True


class SwitchUpscalerCommand(BaseCommand):
    """切换高分修复放大器命令 - /upscaler [name]"""

    command_name = "upscaler"
    command_description = "查看或切换高分修复放大器（hr_upscaler）"
    command_pattern = r"^/upscaler(?:\s+(?P<name>.+))?$"

    async def execute(self) -> Tuple[bool, str, bool]:
        global _active_upscaler
        try:
            upscaler_name = (self.matched_groups.get("name") or "").strip()
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            client = StableDiffusionClient(base_url=api_url)

            if not upscaler_name:
                # 无参数：从 API 拉取列表
                upscalers = await client.get_upscalers()
                if upscalers is None:
                    available = self.get_config("generation.available_upscalers", [])
                    if available:
                        current = _active_upscaler or self.get_config("generation.hr_upscaler", "Latent")
                        lines = ["可用的放大器（来自配置文件）：", ""]
                        for u in available:
                            marker = " ✓（当前）" if u == current else ""
                            lines.append(f"  {u}{marker}")
                        lines.append("\n用法: /upscaler <放大器名>")
                        await self.send_text("\n".join(lines))
                    else:
                        await self.send_text("❌ 获取放大器列表失败，且配置文件中未设置可用放大器列表")
                    return False, "获取放大器列表失败", True

                current = _active_upscaler or self.get_config("generation.hr_upscaler", "Latent")
                lines = ["可用的高分修复放大器（来自 SD API）：", ""]
                for u in upscalers:
                    name = u.get("name", "")
                    marker = " ✓（当前）" if name == current else ""
                    lines.append(f"  {name}{marker}")
                lines.append("\n用法: /upscaler <放大器名>\n注意：仅在启用高分修复（enable_hr=true）时生效。")
                await self.send_text("\n".join(lines))
                return True, "显示放大器列表", True

            # 有参数：切换放大器
            _active_upscaler = upscaler_name
            logger.info("切换放大器: %s", upscaler_name)
            await self.send_text(
                f"✅ 已切换到放大器: {upscaler_name}\n下次启用高分修复的绘图请求将使用此放大器。"
            )
            return True, f"切换到放大器: {upscaler_name}", True

        except Exception as e:
            await self.send_text(f"❌ 切换放大器时出错: {e}")
            return False, f"执行出错: {e}", True
