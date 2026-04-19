"""AI 绘图插件主文件"""
from typing import List, Tuple, Type
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
)
from .actions import AIDrawingAction
from .commands import (
    DrawCommand,
    DrawHelpCommand,
    CurrentModelCommand,
    SwitchModelCommand,
    SwitchSamplerCommand,
    SwitchSchedulerCommand,
)
from .config import CONFIG_SCHEMA, CONFIG_SECTION_DESCRIPTIONS


@register_plugin
class AIDrawingPlugin(BasePlugin):
    """AI 绘图插件 - 基于 Stable Diffusion WebUI API"""

    # 插件基本信息
    plugin_name = "ai_drawing_plugin"
    enable_plugin = True
    dependencies = []
    python_dependencies = ["aiohttp"]
    config_file_name = "config.toml"

    # 配置节描述
    config_section_descriptions = CONFIG_SECTION_DESCRIPTIONS

    # 配置 Schema
    config_schema = CONFIG_SCHEMA

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件包含的组件列表"""
        # 获取 Action 组件的基本信息
        action_info = AIDrawingAction.get_action_info()

        # 读取机器人外观描述配置
        bot_appearance = self.get_config("bot.appearance_description", "")

        # 动态构建 action_require，将外观描述嵌入其中
        if bot_appearance:
            # 创建新的 action_require，包含实际的外观描述
            custom_require = [
                "当用户明确要求生成图片、绘画、画图时使用",
                "当用户描述了想要的图像内容时使用",
                f"当用户要求画你自己、画自画像、画机器人自己时，必须使用以下外观描述作为 prompt 参数：{bot_appearance}",
                "重要：prompt 参数必须使用英文标签，不要使用中文。将用户的中文描述转换为英文标签",
                "标签示例：人物特征(loli, girl, boy)、发色(white hair, black hair, blonde hair)、发型(long hair, short hair, twin tails, ponytail)、眼睛(red eyes, blue eyes, green eyes)、服装(dress, school uniform, maid outfit)、动作(standing, sitting, running, smiling)、配饰(cat ears, glasses, ribbon, hat)",
            ]
            # 修改 action_info 的 action_require
            action_info.action_require = custom_require

        return [
            # Action 组件
            (action_info, AIDrawingAction),
            # Command 组件
            (DrawCommand.get_command_info(), DrawCommand),
            (DrawHelpCommand.get_command_info(), DrawHelpCommand),
            (CurrentModelCommand.get_command_info(), CurrentModelCommand),
            (SwitchModelCommand.get_command_info(), SwitchModelCommand),
            (SwitchSamplerCommand.get_command_info(), SwitchSamplerCommand),
            (SwitchSchedulerCommand.get_command_info(), SwitchSchedulerCommand),
        ]
