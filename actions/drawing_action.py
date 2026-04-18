"""AI 绘图 Action 组件"""
from typing import Tuple
from src.plugin_system import BaseAction, ActionActivationType
from ..sd_client import StableDiffusionClient
from ..utils import MessageGenerator


class AIDrawingAction(BaseAction):
    """AI 绘图 Action - 智能绘图动作"""

    # === 基本信息 ===
    action_name = "ai_drawing"
    action_description = "使用 Stable Diffusion 生成 AI 图像"
    activation_type = ActionActivationType.ALWAYS  # 始终激活

    # === 功能描述 ===
    action_parameters = {
        "prompt": "图像的内容描述词，必须使用英文标签（tags），用逗号分隔。例如: loli, kawaii, white hair, long hair, cat ears, red eyes, short two side up, cat_tail, smile, standing",
        "content_prompt": "内容提示词（可选，用于补充内容描述，也必须使用英文）",
        "width": "图像宽度（可选，默认使用配置文件）",
        "height": "图像高度（可选，默认使用配置文件）",
        "enable_hr": "是否启用高分修复（可选，默认使用配置文件）",
    }

    action_require = [
        "当用户明确要求生成图片、绘画、画图时使用",
        "当用户描述了想要的图像内容时使用",
        "当用户要求画你自己、画自画像、画机器人自己时，请在 prompt 中使用机器人的外观描述。机器人外观：a cute anime girl with blue hair and blue eyes, smiling, wearing a white dress（这是默认外观，实际外观请从配置文件 bot.appearance_description 读取）",
        "重要：prompt 参数必须使用英文标签，不要使用中文。将用户的中文描述转换为英文标签",
        "标签示例：人物特征(loli, girl, boy)、发色(white hair, black hair, blonde hair)、发型(long hair, short hair, twin tails, ponytail)、眼睛(red eyes, blue eyes, green eyes)、服装(dress, school uniform, maid outfit)、动作(standing, sitting, running, smiling)、配饰(cat ears, glasses, ribbon, hat)",
    ]

    action_examples = [
        {
            "user_input": "画一个可爱的猫耳萝莉，白色长发，红色眼睛",
            "action_data": {
                "prompt": "loli, kawaii, cat ears, white hair, long hair, red eyes, smile, cute",
            }
        },
        {
            "user_input": "帮我画一张风景画，有山有水",
            "action_data": {
                "prompt": "landscape, mountain, river, nature, scenery, beautiful",
            }
        },
        {
            "user_input": "画一个穿女仆装的女孩",
            "action_data": {
                "prompt": "girl, maid outfit, maid dress, apron, smile, standing",
            }
        },
    ]
    associated_types = ["text", "image"]

    async def execute(self) -> Tuple[bool, str]:
        """执行 AI 绘图动作"""
        try:
            # 获取配置
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            quality_prompt = self.get_config("generation.quality_prompt", "")
            config_content_prompt = self.get_config("generation.content_prompt", "")
            default_negative = self.get_config("generation.negative_prompt", "")
            default_width = self.get_config("generation.width", 512)
            default_height = self.get_config("generation.height", 512)
            default_steps = self.get_config("generation.steps", 20)
            default_cfg = self.get_config("generation.cfg_scale", 7.0)
            default_sampler = self.get_config("generation.sampler_name", "Euler a")
            default_scheduler = self.get_config("generation.scheduler", None)
            default_enable_hr = self.get_config("generation.enable_hr", False)
            hr_scale = self.get_config("generation.hr_scale", 2.0)
            hr_upscaler = self.get_config("generation.hr_upscaler", "Latent")
            denoising_strength = self.get_config("generation.denoising_strength", 0.7)
            bot_appearance = self.get_config("bot.appearance_description", "")

            # 获取 Action 参数
            user_prompt = self.action_data.get("prompt", "")
            action_content_prompt = self.action_data.get("content_prompt", "")
            width = self.action_data.get("width", default_width)
            height = self.action_data.get("height", default_height)
            enable_hr = self.action_data.get("enable_hr", default_enable_hr)

            # 如果用户要求画自画像，使用机器人外观描述
            if "自画像" in user_prompt or "画你自己" in user_prompt or "画自己" in user_prompt:
                if bot_appearance:
                    user_prompt = bot_appearance
                else:
                    await self.send_text("抱歉，我还没有设置自己的外观描述呢~")
                    return False, "未设置机器人外观描述"

            # 组合 prompt
            # 优先级: 质量提示词 > Action内容提示词 > 配置内容提示词 > 用户提示词
            prompt_parts = []
            if quality_prompt:
                prompt_parts.append(quality_prompt)
            if action_content_prompt:
                prompt_parts.append(action_content_prompt)
            elif config_content_prompt:
                prompt_parts.append(config_content_prompt)
            if user_prompt:
                prompt_parts.append(user_prompt)

            final_prompt = ", ".join(prompt_parts)

            # Debug 模式：显示 prompt 信息
            debug_mode = self.get_config("plugin.debug_mode", False)
            if debug_mode:
                debug_info = f"""🔍 调试信息 (Action组件)
━━━━━━━━━━━━━━━━━━━━━━
📝 Prompt 组合:
  质量提示词: {quality_prompt if quality_prompt else '(无)'}
  Action内容提示词: {action_content_prompt if action_content_prompt else '(无)'}
  配置内容提示词: {config_content_prompt if config_content_prompt else '(无)'}
  用户提示词: {user_prompt if user_prompt else '(无)'}

✅ 最终正面提示词:
{final_prompt}

❌ 负面提示词:
{default_negative}

⚙️ 生成参数:
  尺寸: {width}x{height}
  步数: {default_steps}
  CFG: {default_cfg}
  采样器: {default_sampler}
  调度器: {default_scheduler if default_scheduler else 'Automatic'}
  高分修复: {'是' if enable_hr else '否'}
━━━━━━━━━━━━━━━━━━━━━━"""
                await self.send_text(debug_info)

            # 使用 LLM 生成开始绘图的风格化回复
            start_message = await MessageGenerator.generate_stylized_message(
                "start",
                chat_stream=self.chat_stream,
                user_prompt=user_prompt
            )
            await self.send_text(start_message)

            # 创建客户端并生成图像
            client = StableDiffusionClient(base_url=api_url)
            result = await client.txt2img(
                prompt=final_prompt,
                negative_prompt=default_negative,
                width=width,
                height=height,
                steps=default_steps,
                cfg_scale=default_cfg,
                sampler_name=default_sampler,
                scheduler=default_scheduler,
                enable_hr=enable_hr,
                hr_scale=hr_scale,
                hr_upscaler=hr_upscaler,
                denoising_strength=denoising_strength,
            )

            if result and result.get("images"):
                # 获取第一张图像
                image_base64 = result["images"][0]

                # 发送图像
                await self.send_image(image_base64)

                # 使用 LLM 生成成功的风格化回复
                success_message = await MessageGenerator.generate_stylized_message(
                    "success",
                    chat_stream=self.chat_stream,
                    user_prompt=user_prompt
                )
                await self.send_text(success_message)

                return True, "成功生成并发送图片"
            else:
                # 使用 LLM 生成失败的风格化回复
                fail_message = await MessageGenerator.generate_stylized_message(
                    "fail",
                    chat_stream=self.chat_stream,
                    user_prompt=user_prompt
                )
                await self.send_text(fail_message)
                return False, "图片生成失败"

        except Exception as e:
            # 使用 LLM 生成错误的风格化回复
            error_message = await MessageGenerator.generate_stylized_message(
                "error",
                chat_stream=self.chat_stream,
                error=str(e)
            )
            await self.send_text(error_message)
            return False, f"执行出错: {str(e)}"
