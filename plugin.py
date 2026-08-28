"""AI 绘图插件主文件"""
from typing import List, Tuple, Type
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
)
from .actions import AIDrawingAction
from .actions.recall_action import RecallAction
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
from .commands.recall_command import RecallCommand
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
            "【prompt 组装规则】prompt 必须全部使用英文，按顺序用逗号加空格拼接三层：<hard_tags>, <soft_phrases>, <nltags_block>（尖括号仅表示层次占位，输出时不要写尖括号）",
            "【第一层 hard_tags】离散英文标签放最前，顺序：人数(1girl/1boy/2girls 等)→角色名→作品名→画师(@artist name)→外观→服装→道具→场景；小写英文、空格分词（red hair 而不是 red_hair）、逗号分隔；命名角色须带 2-4 个身份锚点；只写高置信度标签，同类外观只保留 2-4 个，删除弱相关/重复/解释性标签；不确定的复合概念不伪造，降级为自然语言描述",
            "【第二层 soft_phrases】短视觉/审美短语放中间，逗号并列：动作情感、环境氛围、光影动效、画风倾向，必须服务于当前画面情境",
            "【第三层 nltags_block】完整英文短句放最后（至少 1 句），句首用 Place/Use/Keep/Frame/Light/Blur 之一，覆盖位置绑定、手与道具精确接触、视线引导、光源方向、景深虚化、色彩氛围、动作可见后果、脸部可读性；禁止写离散标签列表、世界观解释、心理描写、文学比喻、重复 hard_tags 锚点；每句必须能改变画面",
            "【禁止质量词】严禁自行添加 masterpiece、best quality、highly detailed、score_9 等任何质量前缀，系统已内置默认质量提示词，重复会冲突",
            "【语义分离】同一语义只放一处，禁止跨层重复",
            "【冲突检查】每组只能二选一：solo/多人、close-up/full body、from above/from below、from front/from behind、closed eyes/looking at viewer、裸体/服装；多角色外观逐人绑定不串人；光源与背景同空间；单人正面默认保留 looking at viewer",
            "【完整性】用户描述的画面元素完整保留不弱化；描述模糊时构建情境因果链只取最有张力瞬间；每个关键动作至少一个可见后果；环境必须影响主体；情绪落到表情/视线/手势/重心；至少覆盖 3 个画面维度（互动、情感、视线、环境联动、动势、空间层次、材质质感、因果可见性）",
            "【权重规则】默认不加权；仅用户要求或元素不稳定时才加权，同一 prompt 最多 1-3 个加权点",
            "标签示例：人物特征(loli, girl, boy)、发色(white hair, black hair, blonde hair)、发型(long hair, short hair, twin tails, ponytail)、眼睛(red eyes, blue eyes, green eyes)、服装(dress, school uniform, maid outfit)、动作(standing, sitting, running, smiling)、配饰(cat ears, glasses, ribbon, hat)",
        ])

        # 添加画师风格说明
        if styles_enabled and available_styles:
            style_list = ", ".join([f"'{name}'" for name in available_styles.keys()])
            style_details = "\n".join([f"  - {name}: {tags}" for name, tags in available_styles.items()])
            custom_require.append(
                f"画师风格功能已启用！当用户在对话中明确指定使用某个风格时（如'用动漫风格画'、'用写实风格'等），需要在 style 参数中填写对应的风格名称。可用风格列表: {style_list}。各风格对应的标签如下:\n{style_details}\n注意：只有用户明确指定风格时才填写 style 参数，如果用户没有指定风格，则不要填写 style 参数（留空或不传）"
            )
            custom_require.append(
                "注意：当 style 参数已指定画师风格时，hard_tags 中不要再单独添加 @artist 画师 tag，避免画师标签重复冲突"
            )
        else:
            custom_require.append(
                "画师风格功能未启用，用户无法指定风格"
            )

        # 追加行为约束
        custom_require.extend([
            "【禁止行为】每次对话中此绘图插件只能被调用一次。调用结束后无论成功还是失败，你都必须停止并等待用户的下一条指令，绝对不允许在同一轮对话中再次调用此插件。",
            "【禁止行为】当你已经发送了绘图失败的消息之后，严禁再次自行调用此绘图插件重试。只有当用户在看到你的失败消息后，主动发出新的绘图指令时，才可以再次调用。",
            "重要：在生成涉及人物的图像时，如果用户没有明确描述服装，必须在 prompt 中主动添加日常服饰相关标签（如 t-shirt、dress、jacket、school uniform、casual clothes 等），禁止遗漏服装描述，以避免模型生成裸体图像。",
        ])

        # 修改 action_info 的 action_require
        action_info.action_require = custom_require

        return [
            # Action 组件
            (action_info, AIDrawingAction),
            (RecallAction.get_action_info(), RecallAction),
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
            # 撤回命令
            (RecallCommand.get_command_info(), RecallCommand),
        ]
