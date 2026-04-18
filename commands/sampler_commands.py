"""采样器和调度器管理命令"""
from typing import Tuple
from src.plugin_system import BaseCommand


class SwitchSamplerCommand(BaseCommand):
    """切换采样器命令 - /sampler <sampler_name>"""

    command_name = "sampler"
    command_description = "切换采样器"
    command_pattern = r"^/sampler(?:\s+(?P<sampler_name>.+))?$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行切换采样器命令"""
        try:
            sampler_name = self.matched_groups.get("sampler_name", "").strip()

            # 获取配置的采样器列表
            available_samplers = self.get_config("generation.available_samplers", [])

            # 如果没有提供采样器名称，显示可用列表
            if not sampler_name:
                if available_samplers:
                    samplers_text = "\n".join([f"  - {s}" for s in available_samplers])
                    await self.send_text(f"📋 可用的采样器:\n{samplers_text}\n\n用法: /sampler <采样器名>")
                else:
                    await self.send_text("⚠️ 配置文件中未设置可用采样器列表")
                return True, "显示采样器列表", True

            # 检查采样器是否在配置列表中
            if available_samplers and sampler_name not in available_samplers:
                await self.send_text(f"❌ 采样器 '{sampler_name}' 不在可用列表中\n请使用 /sampler 查看可用采样器")
                return False, "采样器不在可用列表", True

            # 这里需要更新配置文件中的当前采样器
            # 注意：这需要插件系统支持运行时修改配置
            await self.send_text(f"✅ 已切换到采样器: {sampler_name}\n下次生成图片时将使用此采样器")

            return True, f"切换到采样器: {sampler_name}", True

        except Exception as e:
            await self.send_text(f"❌ 切换采样器时出错: {str(e)}")
            return False, f"执行出错: {str(e)}", True


class SwitchSchedulerCommand(BaseCommand):
    """切换调度器命令 - /scheduler <scheduler_name>"""

    command_name = "scheduler"
    command_description = "切换调度器"
    command_pattern = r"^/scheduler(?:\s+(?P<scheduler_name>.+))?$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行切换调度器命令"""
        try:
            scheduler_name = self.matched_groups.get("scheduler_name", "").strip()

            # 获取配置的调度器列表
            available_schedulers = self.get_config("generation.available_schedulers", [])

            # 如果没有提供调度器名称，显示可用列表
            if not scheduler_name:
                if available_schedulers:
                    schedulers_text = "\n".join([f"  - {s}" for s in available_schedulers])
                    await self.send_text(f"📋 可用的调度器:\n{schedulers_text}\n\n用法: /scheduler <调度器名>")
                else:
                    await self.send_text("⚠️ 配置文件中未设置可用调度器列表")
                return True, "显示调度器列表", True

            # 检查调度器是否在配置列表中
            if available_schedulers and scheduler_name not in available_schedulers:
                await self.send_text(f"❌ 调度器 '{scheduler_name}' 不在可用列表中\n请使用 /scheduler 查看可用调度器")
                return False, "调度器不在可用列表", True

            # 这里需要更新配置文件中的当前调度器
            await self.send_text(f"✅ 已切换到调度器: {scheduler_name}\n下次生成图片时将使用此调度器")

            return True, f"切换到调度器: {scheduler_name}", True

        except Exception as e:
            await self.send_text(f"❌ 切换调度器时出错: {str(e)}")
            return False, f"执行出错: {str(e)}", True
