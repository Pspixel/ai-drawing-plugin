"""模型管理命令"""
from typing import Tuple
from src.plugin_system import BaseCommand
from ..sd_client import StableDiffusionClient


class CurrentModelCommand(BaseCommand):
    """查看当前模型命令 - /drawmodel"""

    command_name = "drawmodel"
    command_description = "查看当前使用的 Stable Diffusion 模型"
    command_pattern = r"^/drawmodel$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行查看当前模型命令"""
        try:
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            client = StableDiffusionClient(base_url=api_url)

            current_model = await client.get_current_model()

            if current_model:
                await self.send_text(f"📦 当前使用的模型: {current_model}")
                return True, f"当前模型: {current_model}", True
            else:
                await self.send_text("❌ 无法获取当前模型信息")
                return False, "获取模型信息失败", True

        except Exception as e:
            await self.send_text(f"❌ 查询模型时出错: {str(e)}")
            return False, f"执行出错: {str(e)}", True


class SwitchModelCommand(BaseCommand):
    """切换模型命令 - /switchmodel <model_name>"""

    command_name = "switchmodel"
    command_description = "切换 Stable Diffusion 模型"
    command_pattern = r"^/switchmodel\s+(?P<model_name>.+)$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行切换模型命令"""
        try:
            model_name = self.matched_groups.get("model_name", "").strip()

            if not model_name:
                await self.send_text("请提供模型名称！\n用法: /switchmodel <模型名>")
                return False, "缺少模型名称", True

            api_url = self.get_config("api.base_url", "http://localhost:7860")
            client = StableDiffusionClient(base_url=api_url)

            await self.send_text(f"正在切换到模型: {model_name}...")

            success = await client.switch_model(model_name)

            if success:
                await self.send_text(f"✅ 成功切换到模型: {model_name}")
                return True, f"切换到模型: {model_name}", True
            else:
                await self.send_text(f"❌ 切换模型失败，请检查模型名称是否正确")
                return False, "切换模型失败", True

        except Exception as e:
            await self.send_text(f"❌ 切换模型时出错: {str(e)}")
            return False, f"执行出错: {str(e)}", True
