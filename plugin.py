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
        return [
            # Action 组件
            (AIDrawingAction.get_action_info(), AIDrawingAction),
            # Command 组件
            (DrawCommand.get_command_info(), DrawCommand),
            (DrawHelpCommand.get_command_info(), DrawHelpCommand),
            (CurrentModelCommand.get_command_info(), CurrentModelCommand),
            (SwitchModelCommand.get_command_info(), SwitchModelCommand),
            (SwitchSamplerCommand.get_command_info(), SwitchSamplerCommand),
            (SwitchSchedulerCommand.get_command_info(), SwitchSchedulerCommand),
        ]
