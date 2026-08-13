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
    SwitchUpscalerCommand,
    ListModulesCommand,
    AddModuleCommand,
    RemoveModuleCommand,
    ClearModulesCommand,
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

        # 读取画师风格配置
        styles_enabled = self.get_config("artist_styles.enabled", False)
        available_styles = self.get_config("artist_styles.styles", {})

        # 动态构建 action_require，将外观描述和风格列表嵌入其中
        custom_require = [
            "当用户明确要求生成图片、绘画、画图时使用",
            "当用户描述了想要的图像内容时使用",
        ]

        # 添加自画像说明
        if bot_appearance:
            custom_require.append(
                f"当用户要求画你自己、画自画像、画机器人自己时，必须使用以下外观描述作为 prompt 参数：{bot_appearance}"
            )
        else:
            custom_require.append(
                "当用户要求画你自己、画自画像、画机器人自己时，必须从配置文件 bot.appearance_description 读取机器人外观描述，并将其作为 prompt 参数传入"
            )

        custom_require.extend([
            "重要：prompt 参数必须使用英文标签，不要使用中文。将用户的中文描述转换为英文标签",
            "标签示例：人物特征(loli, girl, boy)、发色(white hair, black hair, blonde hair)、发型(long hair, short hair, twin tails, ponytail)、眼睛(red eyes, blue eyes, green eyes)、服装(dress, school uniform, maid outfit)、动作(standing, sitting, running, smiling)、配饰(cat ears, glasses, ribbon, hat)",
        ])

        # 添加画师风格说明
        if styles_enabled and available_styles:
            style_list = ", ".join([f"'{name}'" for name in available_styles.keys()])
            style_details = "\n".join([f"  - {name}: {tags}" for name, tags in available_styles.items()])
            custom_require.append(
                f"画师风格功能已启用！当用户在对话中明确指定使用某个风格时（如'用动漫风格画'、'用写实风格'等），需要在 style 参数中填写对应的风格名称。可用风格列表: {style_list}。各风格对应的标签如下:\n{style_details}\n注意：只有用户明确指定风格时才填写 style 参数，如果用户没有指定风格，则不要填写 style 参数（留空或不传）"
            )
        else:
            custom_require.append(
                "画师风格功能未启用，用户无法指定风格"
            )

        # 追加行为约束
        custom_require.extend([
            "重要：绘图失败或结果不理想时，除非用户明确要求重试或重新生成，否则禁止自行再次调用此插件绘图。",
            "重要：在生成涉及人物的图像时，如果用户没有明确描述服装，必须在 prompt 中主动添加日常服饰相关标签（如 t-shirt、dress、jacket、school uniform、casual clothes 等），禁止遗漏服装描述，以避免模型生成裸体图像。",
        ])

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
            (SwitchUpscalerCommand.get_command_info(), SwitchUpscalerCommand),
            # 附加模块管理命令
            (ListModulesCommand.get_command_info(), ListModulesCommand),
            (AddModuleCommand.get_command_info(), AddModuleCommand),
            (RemoveModuleCommand.get_command_info(), RemoveModuleCommand),
            (ClearModulesCommand.get_command_info(), ClearModulesCommand),
        ]
