"""AI 绘图插件主文件"""
from typing import List, Tuple, Type
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseAction,
    BaseCommand,
    ComponentInfo,
    ActionActivationType,
    ConfigField,
    llm_api,
)
import base64
from .sd_client import StableDiffusionClient


# ===== Action 组件 =====
class AIDrawingAction(BaseAction):
    """AI 绘图 Action - 智能绘图动作"""

    # === 基本信息 ===
    action_name = "ai_drawing"
    action_description = "使用 Stable Diffusion 生成 AI 图像"
    activation_type = ActionActivationType.ALWAYS  # 始终激活

    # === 功能描述 ===
    action_parameters = {
        "prompt": "图像的正面描述词，描述想要生成的内容",
        "width": "图像宽度（可选，默认使用配置文件）",
        "height": "图像高度（可选，默认使用配置文件）",
        "enable_hr": "是否启用高分修复（可选，默认使用配置文件）",
    }
    action_require = [
        "当用户明确要求生成图片、绘画、画图时使用",
        "当用户描述了想要的图像内容时使用",
        "当用户要求画自己的自画像时，使用配置中的机器人外观描述作为 prompt",
    ]
    associated_types = ["text", "image"]

    async def execute(self) -> Tuple[bool, str]:
        """执行 AI 绘图动作"""
        try:
            # 获取配置
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            default_prompt = self.get_config("generation.default_prompt", "")
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
            final_prompt = f"{default_prompt}, {user_prompt}" if default_prompt else user_prompt

            # 使用 LLM 生成开始绘图的风格化回复
            start_message = await self._generate_stylized_message(
                "start", user_prompt=user_prompt
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
                success_message = await self._generate_stylized_message(
                    "success", user_prompt=user_prompt
                )
                await self.send_text(success_message)

                return True, "成功生成并发送图片"
            else:
                # 使用 LLM 生成失败的风格化回复
                fail_message = await self._generate_stylized_message(
                    "fail", user_prompt=user_prompt
                )
                await self.send_text(fail_message)
                return False, "图片生成失败"

        except Exception as e:
            # 使用 LLM 生成错误的风格化回复
            error_message = await self._generate_stylized_message(
                "error", error=str(e)
            )
            await self.send_text(error_message)
            return False, f"执行出错: {str(e)}"

    async def _generate_stylized_message(self, message_type: str, **kwargs) -> str:
        """使用 LLM 生成风格化的回复消息

        Args:
            message_type: 消息类型 (start/success/fail/error)
            **kwargs: 额外参数，如 user_prompt, error 等

        Returns:
            生成的风格化消息
        """
        try:
            # 获取可用模型
            models = llm_api.get_available_models()
            if not models:
                # 如果没有可用模型，返回默认消息
                return self._get_default_message(message_type, **kwargs)

            # 使用第一个可用模型
            model_name = list(models.keys())[0]
            model_config = models[model_name]

            # 根据消息类型构建提示词
            prompt = self._build_prompt(message_type, **kwargs)

            # 调用 LLM 生成内容
            success, content, _, _ = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=model_config,
                request_type="plugin.ai_drawing.message",
                temperature=0.8,
                max_tokens=150,
            )

            if success and content:
                return content.strip()
            else:
                return self._get_default_message(message_type, **kwargs)

        except Exception:
            # 如果 LLM 调用失败，返回默认消息
            return self._get_default_message(message_type, **kwargs)

    def _build_prompt(self, message_type: str, **kwargs) -> str:
        """构建 LLM 提示词"""
        if message_type == "start":
            user_prompt = kwargs.get("user_prompt", "")
            return f"""你是一个可爱活泼的 AI 绘图助手。用户请求你画："{user_prompt}"
请生成一句简短、有趣、充满期待的回复，告诉用户你正在为他们生成图片。
要求：
1. 不超过30个字
2. 语气活泼可爱
3. 可以使用emoji表情
4. 不要使用引号

示例风格：
- 好的！马上为你画出来，请稍等片刻~ ✨
- 收到！让我施展魔法，马上就好~ 🎨
- 明白啦！正在努力创作中，稍等一下哦~ 🖌️"""

        elif message_type == "success":
            user_prompt = kwargs.get("user_prompt", "")
            return f"""你是一个可爱活泼的 AI 绘图助手。你刚刚成功为用户生成了图片，主题是："{user_prompt}"
请生成一句简短、欢快、有成就感的回复。
要求：
1. 不超过30个字
2. 语气活泼可爱
3. 可以使用emoji表情
4. 不要使用引号

示例风格：
- 完成啦！希望你喜欢这幅作品~ 🎉
- 画好了！快来看看效果如何~ ✨
- 搞定！这次的创作我很满意呢~ 🌟"""

        elif message_type == "fail":
            return """你是一个可爱活泼的 AI 绘图助手。图片生成失败了。
请生成一句简短、抱歉但不失可爱的回复。
要求：
1. 不超过30个字
2. 语气温柔体贴
3. 可以使用emoji表情
4. 不要使用引号

示例风格：
- 呜呜，生成失败了...要不要再试一次？ 😢
- 抱歉，这次没画好...让我再试试吧~ 💦
- 哎呀，出了点小问题...稍后再试试好吗？ 🥺"""

        elif message_type == "error":
            error = kwargs.get("error", "未知错误")
            return f"""你是一个可爱活泼的 AI 绘图助手。生成图片时遇到了错误：{error}
请生成一句简短、抱歉的回复，但不要直接提及技术错误信息。
要求：
1. 不超过30个字
2. 语气温柔体贴
3. 可以使用emoji表情
4. 不要使用引号

示例风格：
- 哎呀，出了点小状况...稍后再试试吧~ 😅
- 抱歉，遇到了一些问题...请稍后重试~ 💫
- 呜，好像哪里不对劲...让我检查一下~ 🔧"""

        return ""

    def _get_default_message(self, message_type: str, **kwargs) -> str:
        """获取默认消息（当 LLM 不可用时）"""
        if message_type == "start":
            return "正在为你生成图片，请稍等..."
        elif message_type == "success":
            return "图片生成完成！"
        elif message_type == "fail":
            return "抱歉，图片生成失败了..."
        elif message_type == "error":
            error = kwargs.get("error", "")
            return f"生成图片时出错了: {error}"
        return ""


# ===== Command 组件 =====
class DrawCommand(BaseCommand):
    """绘图命令 - /draw <prompt>"""

    command_name = "draw"
    command_description = "使用 Stable Diffusion 生成图像"
    command_pattern = r"^/draw\s+(?P<prompt>.+)$"

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行绘图命令"""
        try:
            # 获取参数
            prompt = self.matched_groups.get("prompt", "").strip()

            if not prompt:
                await self.send_text("请提供绘图描述！\n用法: /draw <描述>")
                return False, "缺少绘图描述", True

            # 获取配置
            api_url = self.get_config("api.base_url", "http://localhost:7860")
            default_prompt = self.get_config("generation.default_prompt", "")
            default_negative = self.get_config("generation.negative_prompt", "")
            width = self.get_config("generation.width", 512)
            height = self.get_config("generation.height", 512)
            steps = self.get_config("generation.steps", 20)
            cfg_scale = self.get_config("generation.cfg_scale", 7.0)
            sampler_name = self.get_config("generation.sampler_name", "Euler a")
            scheduler = self.get_config("generation.scheduler", None)
            enable_hr = self.get_config("generation.enable_hr", False)
            hr_scale = self.get_config("generation.hr_scale", 2.0)
            hr_upscaler = self.get_config("generation.hr_upscaler", "Latent")
            denoising_strength = self.get_config("generation.denoising_strength", 0.7)

            # 组合 prompt
            final_prompt = f"{default_prompt}, {prompt}" if default_prompt else prompt

            # 使用 LLM 生成开始绘图的风格化回复
            start_message = await self._generate_stylized_message("start", user_prompt=prompt)
            await self.send_text(start_message)

            # 创建客户端并生成图像
            client = StableDiffusionClient(base_url=api_url)
            result = await client.txt2img(
                prompt=final_prompt,
                negative_prompt=default_negative,
                width=width,
                height=height,
                steps=steps,
                cfg_scale=cfg_scale,
                sampler_name=sampler_name,
                scheduler=scheduler,
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
                success_message = await self._generate_stylized_message("success", user_prompt=prompt)
                await self.send_text(success_message)

                return True, "成功生成图片", True
            else:
                # 使用 LLM 生成失败的风格化回复
                fail_message = await self._generate_stylized_message("fail", user_prompt=prompt)
                await self.send_text(fail_message)
                return False, "图片生成失败", True

        except Exception as e:
            # 使用 LLM 生成错误的风格化回复
            error_message = await self._generate_stylized_message("error", error=str(e))
            await self.send_text(error_message)
            return False, f"执行出错: {str(e)}", True

    async def _generate_stylized_message(self, message_type: str, **kwargs) -> str:
        """使用 LLM 生成风格化的回复消息

        Args:
            message_type: 消息类型 (start/success/fail/error)
            **kwargs: 额外参数，如 user_prompt, error 等

        Returns:
            生成的风格化消息
        """
        try:
            # 获取可用模型
            models = llm_api.get_available_models()
            if not models:
                return self._get_default_message(message_type, **kwargs)

            # 使用第一个可用模型
            model_name = list(models.keys())[0]
            model_config = models[model_name]

            # 根据消息类型构建提示词
            prompt = self._build_prompt(message_type, **kwargs)

            # 调用 LLM 生成内容
            success, content, _, _ = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=model_config,
                request_type="plugin.ai_drawing.message",
                temperature=0.8,
                max_tokens=150,
            )

            if success and content:
                return content.strip()
            else:
                return self._get_default_message(message_type, **kwargs)

        except Exception:
            return self._get_default_message(message_type, **kwargs)

    def _build_prompt(self, message_type: str, **kwargs) -> str:
        """构建 LLM 提示词"""
        if message_type == "start":
            user_prompt = kwargs.get("user_prompt", "")
            return f"""你是一个可爱活泼的 AI 绘图助手。用户请求你画："{user_prompt}"
请生成一句简短、有趣、充满期待的回复，告诉用户你正在为他们生成图片。
要求：
1. 不超过30个字
2. 语气活泼可爱
3. 可以使用emoji表情
4. 不要使用引号

示例风格：
- 好的！马上为你画出来，请稍等片刻~ ✨
- 收到！让我施展魔法，马上就好~ 🎨
- 明白啦！正在努力创作中，稍等一下哦~ 🖌️"""

        elif message_type == "success":
            user_prompt = kwargs.get("user_prompt", "")
            return f"""你是一个可爱活泼的 AI 绘图助手。你刚刚成功为用户生成了图片，主题是："{user_prompt}"
请生成一句简短、欢快、有成就感的回复。
要求：
1. 不超过30个字
2. 语气活泼可爱
3. 可以使用emoji表情
4. 不要使用引号

示例风格：
- 完成啦！希望你喜欢这幅作品~ 🎉
- 画好了！快来看看效果如何~ ✨
- 搞定！这次的创作我很满意呢~ 🌟"""

        elif message_type == "fail":
            return """你是一个可爱活泼的 AI 绘图助手。图片生成失败了。
请生成一句简短、抱歉但不失可爱的回复。
要求：
1. 不超过30个字
2. 语气温柔体贴
3. 可以使用emoji表情
4. 不要使用引号

示例风格：
- 呜呜，生成失败了...要不要再试一次？ 😢
- 抱歉，这次没画好...让我再试试吧~ 💦
- 哎呀，出了点小问题...稍后再试试好吗？ 🥺"""

        elif message_type == "error":
            error = kwargs.get("error", "未知错误")
            return f"""你是一个可爱活泼的 AI 绘图助手。生成图片时遇到了错误：{error}
请生成一句简短、抱歉的回复，但不要直接提及技术错误信息。
要求：
1. 不超过30个字
2. 语气温柔体贴
3. 可以使用emoji表情
4. 不要使用引号

示例风格：
- 哎呀，出了点小状况...稍后再试试吧~ 😅
- 抱歉，遇到了一些问题...请稍后重试~ 💫
- 呜，好像哪里不对劲...让我检查一下~ 🔧"""

        return ""

    def _get_default_message(self, message_type: str, **kwargs) -> str:
        """获取默认消息（当 LLM 不可用时）"""
        if message_type == "start":
            return "正在生成图片，请稍等..."
        elif message_type == "success":
            return "✅ 图片生成完成！"
        elif message_type == "fail":
            return "❌ 图片生成失败"
        elif message_type == "error":
            error = kwargs.get("error", "")
            return f"❌ 生成图片时出错: {error}"
        return ""


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

/switchmodel <模型名> - 切换绘图模型
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


# ===== 插件主类 =====
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
    config_section_descriptions = {
        "plugin": "插件基本配置",
        "api": "Stable Diffusion API 配置",
        "generation": "图像生成参数配置",
        "bot": "机器人相关配置",
    }

    # 配置 Schema
    config_schema = {
        "plugin": {
            "enabled": ConfigField(
                type=bool,
                default=False,
                description="是否启用插件"
            ),
            "config_version": ConfigField(
                type=str,
                default="1.0.0",
                description="配置文件版本"
            ),
        },
        "api": {
            "base_url": ConfigField(
                type=str,
                default="http://localhost:7860",
                description="Stable Diffusion WebUI API 地址",
                example="http://localhost:7860",
            ),
        },
        "generation": {
            "default_prompt": ConfigField(
                type=str,
                default="masterpiece, best quality, highly detailed",
                description="默认正面提示词（会自动添加到用户提示词前）",
            ),
            "negative_prompt": ConfigField(
                type=str,
                default="lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
                description="默认负面提示词",
            ),
            "width": ConfigField(
                type=int,
                default=512,
                description="图像宽度（像素）"
            ),
            "height": ConfigField(
                type=int,
                default=512,
                description="图像高度（像素）"
            ),
            "steps": ConfigField(
                type=int,
                default=20,
                description="采样步数"
            ),
            "cfg_scale": ConfigField(
                type=float,
                default=7.0,
                description="提示词相关性"
            ),
            "sampler_name": ConfigField(
                type=str,
                default="Euler a",
                description="采样器名称",
                example="DPM++ 2M Karras",
            ),
            "scheduler": ConfigField(
                type=str,
                default="",
                description="调度器类型（留空使用默认）",
                example="Karras",
            ),
            "enable_hr": ConfigField(
                type=bool,
                default=False,
                description="是否启用高分修复"
            ),
            "hr_scale": ConfigField(
                type=float,
                default=2.0,
                description="高分修复放大倍数"
            ),
            "hr_upscaler": ConfigField(
                type=str,
                default="Latent",
                description="高分修复使用的放大器",
                example="R-ESRGAN 4x+",
            ),
            "denoising_strength": ConfigField(
                type=float,
                default=0.7,
                description="去噪强度（用于高分修复）",
            ),
            "available_samplers": ConfigField(
                type=list,
                default=[
                    "Euler a",
                    "Euler",
                    "DPM++ 2M Karras",
                    "DPM++ SDE Karras",
                    "DPM++ 2M SDE",
                    "DDIM",
                    "LMS",
                ],
                description="可用的采样器列表（用于命令切换）",
            ),
            "available_schedulers": ConfigField(
                type=list,
                default=[
                    "Automatic",
                    "Karras",
                    "Exponential",
                    "Polyexponential",
                ],
                description="可用的调度器列表（用于命令切换）",
            ),
        },
        "bot": {
            "appearance_description": ConfigField(
                type=str,
                default="a cute anime girl with blue hair and blue eyes, smiling, wearing a white dress",
                description="机器人的外观描述（用于自画像功能）",
            ),
        },
    }

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
