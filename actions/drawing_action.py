"""AI 绘图 Action 组件"""
import logging
import time
import asyncio
from typing import Tuple
from src.plugin_system import BaseAction, ActionActivationType
from ..utils import MessageGenerator, RecallManager
from ..utils.drawing_queue import DrawingQueue
from ..image_review import ImageReviewer
from ..commands.module_commands import get_active_modules
from ..commands.sampler_commands import get_active_sampler, get_active_scheduler, get_active_upscaler

logger = logging.getLogger("ai_drawing.drawing_action")


class AIDrawingAction(BaseAction):
    """AI 绘图 Action - 智能绘图动作"""

    # === 基本信息 ===
    action_name = "ai_drawing"
    action_description = "使用 Stable Diffusion 生成 AI 图像"
    activation_type = ActionActivationType.ALWAYS  # 始终激活

    # === 功能描述 ===
    action_parameters = {
        "prompt": "图像的内容描述词，必须使用英文标签（tags），用逗号分隔。例如: loli, kawaii, white hair, long hair, cat ears, red eyes, short two side up, cat_tail, smile, standing",
        "style": "画师风格名称（可选，当用户指定风格时填写中文风格名，如 '动漫'、'写实'、'油画' 等）。可用风格列表见 action_require",
        "content_prompt": "内容提示词（可选，用于补充内容描述，也必须使用英文）",
        "width": "图像宽度（可选，默认使用配置文件）",
        "height": "图像高度（可选，默认使用配置文件）",
        "enable_hr": "是否启用高分修复（可选，默认使用配置文件）",
        "hr_second_pass_steps": "高分修复二次采样步数（可选，0 表示与首次步数相同，默认使用配置文件）",
    }

    action_require = [
        "当用户明确要求生成图片、绘画、画图时使用",
        "当用户描述了想要的图像内容时使用",
        "当用户要求画你自己、画自画像、画机器人自己时，必须从配置文件 bot.appearance_description 读取机器人外观描述，并将其作为 prompt 参数传入",
        "重要：prompt 参数必须使用英文标签，不要使用中文。将用户的中文描述转换为英文标签",
        "标签示例：人物特征(loli, girl, boy)、发色(white hair, black hair, blonde hair)、发型(long hair, short hair, twin tails, ponytail)、眼睛(red eyes, blue eyes, green eyes)、服装(dress, school uniform, maid outfit)、动作(standing, sitting, running, smiling)、配饰(cat ears, glasses, ribbon, hat)",
        "画师风格功能：当配置启用了画师风格功能时，用户可以指定使用某个风格（如'用动漫风格画'、'用写实风格'等）。此时需要在 style 参数中填写对应的风格名称",
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
        {
            "user_input": "画你自己",
            "action_data": {
                "prompt": "使用 action_require 中提供的机器人外观描述",
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
            default_sampler = get_active_sampler() or self.get_config("generation.sampler_name", "Euler a")
            default_scheduler = get_active_scheduler() or self.get_config("generation.scheduler", None)
            default_enable_hr = self.get_config("generation.enable_hr", False)
            hr_scale = self.get_config("generation.hr_scale", 2.0)
            hr_upscaler = get_active_upscaler() or self.get_config("generation.hr_upscaler", "Latent")
            hr_second_pass_steps = self.get_config("generation.hr_second_pass_steps", 0)
            denoising_strength = self.get_config("generation.denoising_strength", 0.7)
            bot_appearance = self.get_config("bot.appearance_description", "")

            # 获取画师风格配置
            styles_enabled = self.get_config("artist_styles.enabled", False)
            available_styles = self.get_config("artist_styles.styles", {})

            # 获取 Action 参数
            user_prompt = self.action_data.get("prompt", "")
            action_content_prompt = self.action_data.get("content_prompt", "")
            user_style = self.action_data.get("style", "")
            width = self.action_data.get("width") or default_width
            height = self.action_data.get("height") or default_height
            enable_hr_raw = self.action_data.get("enable_hr")
            enable_hr = default_enable_hr if enable_hr_raw == "" or enable_hr_raw is None else enable_hr_raw
            hr_second_pass_steps_raw = self.action_data.get("hr_second_pass_steps")
            hr_second_pass_steps = hr_second_pass_steps if hr_second_pass_steps_raw == "" or hr_second_pass_steps_raw is None else hr_second_pass_steps_raw

            # 如果用户要求画自画像，使用机器人外观描述
            if "自画像" in user_prompt or "画你自己" in user_prompt or "画自己" in user_prompt:
                if bot_appearance:
                    user_prompt = bot_appearance
                else:
                    await self.send_text("抱歉，我还没有设置自己的外观描述呢~")
                    return False, "未设置机器人外观描述"

            # 处理画师风格（只有用户明确指定时才使用）
            style_tags = ""
            used_style_name = ""
            if styles_enabled and available_styles and user_style:
                # 只有当用户指定了风格时才添加风格标签
                if user_style in available_styles:
                    style_tags = available_styles[user_style]
                    used_style_name = user_style
                    logger.info("使用用户指定的风格: %s -> %s", user_style, style_tags)
                else:
                    logger.warning("用户指定的风格 '%s' 不存在于配置中", user_style)

            # 组合 prompt
            # 优先级: 风格标签 > 质量提示词 > Action内容提示词 > 配置内容提示词 > 用户提示词
            prompt_parts = []
            if style_tags:
                prompt_parts.append(style_tags)
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
  风格标签: {style_tags if style_tags else '(无)'}
  使用风格: {used_style_name if used_style_name else '(无)'}
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
  高分修复步数: {hr_second_pass_steps if hr_second_pass_steps > 0 else f'与首次相同({default_steps})'}
━━━━━━━━━━━━━━━━━━━━━━"""
                await self.send_text(debug_info)

            # 合并默认附加模块和运行时激活的模块（去重保序）
            default_modules = self.get_config("generation.default_additional_modules", [])
            active_modules = get_active_modules()
            final_modules = list(dict.fromkeys(default_modules + active_modules))

            # 组装 txt2img 参数
            txt2img_kwargs = dict(
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
                hr_second_pass_steps=hr_second_pass_steps,
                denoising_strength=denoising_strength,
            )
            if final_modules:
                txt2img_kwargs["forge_additional_modules"] = final_modules

            # 检查队列是否已满，满则提前拒绝
            from ..utils.drawing_queue import QUEUE_MAX_SIZE
            queue_size = DrawingQueue.queue_size()
            if queue_size >= QUEUE_MAX_SIZE:
                await self.send_text(
                    f"绘图队列已满（当前排队 {queue_size} 个任务，最多 {QUEUE_MAX_SIZE} 个），请稍候再发起绘图请求~"
                )
                return False, "绘图队列已满"

            # 如果有排队任务，通知用户
            if queue_size > 0:
                queue_notice = f"已收到绘图请求，前方还有 {queue_size} 个任务在排队，请耐心等待~"
                await self.send_text(queue_notice)

            # 使用 LLM 生成开始绘图的风格化回复
            start_message = await MessageGenerator.generate_stylized_message(
                "start",
                chat_stream=self.chat_stream,
                user_prompt=user_prompt
            )
            await self.send_text(start_message)

            # 将任务放入队列，异步等待执行完成
            success, result, err_msg = await DrawingQueue.enqueue(
                client_base_url=api_url,
                txt2img_kwargs=txt2img_kwargs,
            )

            if not success:
                error_message = await MessageGenerator.generate_stylized_message(
                    "error",
                    chat_stream=self.chat_stream,
                    error=err_msg
                )
                await self.send_text(error_message)
                return False, f"绘图任务失败: {err_msg}"

            if result and result.get("images"):
                # 获取第一张图像
                image_base64 = result["images"][0]

                # 图像审查流程
                if ImageReviewer.should_review(
                    is_group=self.is_group,
                    group_id=self.group_id,
                    user_id=self.user_id,
                    config_getter=self.get_config,
                ):
                    is_safe, reason = await self._review_image(image_base64)
                    if not is_safe:
                        # 图片违规，发送拦截消息
                        block_message = self.get_config(
                            "image_review.block_message",
                            "⚠️ 生成的图片未通过安全审查，已拦截输出。",
                        )
                        if reason:
                            block_message = f"{block_message}\n原因：{reason}"
                        await self.send_text(block_message)
                        return False, f"图片未通过审查: {reason}"

                # 发送图像
                await self.send_image(image_base64)

                # 追踪发送的消息（用于撤回）。发图后稍等 echo，尽量记下整数平台 ID。
                sent_at = time.time()
                RecallManager.track_sent_message(
                    chat_id=self.chat_id,
                    context={
                        "stream_id": self.chat_stream.stream_id,
                        "timestamp": sent_at,
                        "message_type": "image",
                    },
                )
                asyncio.create_task(
                    RecallManager.capture_sent_image(
                        chat_id=self.chat_id,
                        stream_id=self.chat_stream.stream_id,
                        timestamp=sent_at,
                    )
                )

                # 如果启用了自动撤回
                auto_recall_enabled = self.get_config("recall.auto_recall_enabled", False)
                if auto_recall_enabled:
                    auto_recall_delay = self.get_config("recall.auto_recall_delay", 60)
                    napcat_api_url = self.get_config("recall.napcat_api_url", "http://localhost:3000")
                    napcat_api_token = self.get_config("recall.napcat_api_token", "")
                    # 创建异步任务执行延迟撤回
                    asyncio.create_task(
                        self._auto_recall_after_delay(
                            auto_recall_delay, napcat_api_url, napcat_api_token
                        )
                    )

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

    async def _auto_recall_after_delay(
        self, delay: int, napcat_api_url: str, napcat_api_token: str = ""
    ) -> None:
        """延迟后自动撤回消息

        Args:
            delay: 延迟时间（秒）
            napcat_api_url: NapCat API 地址
        """
        try:
            # 等待指定时间
            await asyncio.sleep(delay)

            # 执行撤回
            success, msg = await RecallManager.recall_latest_image(
                chat_id=self.chat_id,
                napcat_api_url=napcat_api_url,
                napcat_api_token=napcat_api_token,
            )

            if success:
                logger.info(f"自动撤回成功: chat_id={self.chat_id}")
            else:
                logger.warning(f"自动撤回失败: chat_id={self.chat_id}, reason={msg}")

        except Exception as e:
            logger.error(f"自动撤回时发生异常: {e}", exc_info=True)

    async def _review_image(self, image_base64: str) -> Tuple[bool, str]:
        """审查图像是否违规

        调用视觉模型 API 对图像进行安全审查。

        Args:
            image_base64: 图片的 base64 编码

        Returns:
            Tuple[bool, str]: (是否安全, 违规原因)
        """
        try:
            vision_api_url = self.get_config(
                "image_review.vision_api_base_url", "http://localhost:11434/v1"
            )
            vision_api_key = self.get_config("image_review.vision_api_key", "")
            vision_model = self.get_config("image_review.vision_model_name", "llava")
            review_prompt = self.get_config("image_review.review_prompt", "")

            is_safe, reason = await ImageReviewer.review_image(
                image_base64=image_base64,
                api_base_url=vision_api_url,
                api_key=vision_api_key,
                model_name=vision_model,
                review_prompt=review_prompt,
            )
            return is_safe, reason or ""

        except Exception as e:
            # 审查服务异常时，默认拦截并返回错误信息
            logger.error("审查过程异常: %s", e)
            error_message = self.get_config(
                "image_review.review_error_message",
                "⚠️ 图像审查服务异常，为安全起见已拦截输出。",
            )
            await self.send_text(error_message)
            return False, "审查服务异常"
