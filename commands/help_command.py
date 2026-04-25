"""帮助命令 - /drawhelp"""
from typing import Tuple
from src.plugin_system import BaseCommand


class DrawHelpCommand(BaseCommand):
    """绘图帮助命令 - /drawhelp"""

    command_name = "drawhelp"
    command_description = "显示 AI 绘图插件的帮助信息"
    command_pattern = r"^/drawhelp$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行帮助命令"""
        help_text = """🎨 AI 绘图插件帮助

📝 可用命令:
/draw <描述> - 生成图片
  示例: /draw a beautiful landscape

/drawmodel - 查看当前使用的模型

/switchmodel [模型名] - 切换绘图模型（不带参数列出可选模型）
  示例: /switchmodel model_name.safetensors

/sampler [采样器名] - 查看或切换采样器
  示例: /sampler DPM++ 2M Karras

/scheduler [调度器名] - 查看或切换调度器
  示例: /scheduler Karras

/drawhelp - 显示此帮助信息

💡 提示:
- 你也可以直接对我说"帮我画一张..."，我会智能识别并生成图片
- 可以在配置文件中调整默认参数"""

        await self.send_text(help_text)
        return True, "显示帮助信息", True
