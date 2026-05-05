"""绘图命令 - /draw"""
import logging
from typing import Tuple
from src.plugin_system import BaseCommand
from ..sd_client import StableDiffusionClient
from ..image_review import ImageReviewer

logger = logging.getLogger("ai_drawing.draw_command")


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
            quality_prompt = self.get_config("generation.quality_prompt", "")
            config_content_prompt = self.get_config("generation.content_prompt", "")
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
            hr_second_pass_steps = self.get_config("generation.hr_second_pass_steps", 0)
            denoising_strength = self.get_config("generation.denoising_strength", 0.7)

            # 组合 prompt
            # 优先级: 质量提示词 > 配置内容提示词 > 用户提示词
            prompt_parts = []
            if quality_prompt:
                prompt_parts.append(quality_prompt)
            if config_content_prompt:
                prompt_parts.append(config_content_prompt)
            if prompt:
                prompt_parts.append(prompt)

            final_prompt = ", ".join(prompt_parts)

            # Debug 模式：显示 prompt 信息
            debug_mode = self.get_config("plugin.debug_mode", False)
            if debug_mode:
                debug_info = f"""🔍 调试信息 (Command组件)
━━━━━━━━━━━━━━━━━━━━━━
📝 Prompt 组合:
  质量提示词: {quality_prompt if quality_prompt else '(无)'}
  配置内容提示词: {config_content_prompt if config_content_prompt else '(无)'}
  用户提示词: {prompt if prompt else '(无)'}

✅ 最终正面提示词:
{final_prompt}

❌ 负面提示词:
{default_negative}

⚙️ 生成参数:
  尺寸: {width}x{height}
  步数: {steps}
  CFG: {cfg_scale}
  采样器: {sampler_name}
  调度器: {scheduler if scheduler else 'Automatic'}
  高分修复: {'是' if enable_hr else '否'}
  高分修复步数: {hr_second_pass_steps if hr_second_pass_steps > 0 else f'与首次相同({steps})'}
━━━━━━━━━━━━━━━━━━━━━━"""
                await self.send_text(debug_info)

            # 发送开始提示
            await self.send_text("正在生成图片，请稍等...")

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
                hr_second_pass_steps=hr_second_pass_steps,
                denoising_strength=denoising_strength,
            )

            if result and result.get("images"):
                # 获取第一张图像
                image_base64 = result["images"][0]

                # 图像审查流程
                if self._should_review():
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
                        return False, f"图片未通过审查: {reason}", True

                # 发送图像
                await self.send_image(image_base64)

                # 发送成功提示
                await self.send_text("✅ 图片生成完成！")

                return True, "成功生成图片", True
            else:
                # 发送失败提示
                await self.send_text("❌ 图片生成失败")
                return False, "图片生成失败", True

        except Exception as e:
            # 发送错误提示
            await self.send_text(f"❌ 生成图片时出错: {str(e)}")
            return False, f"执行出错: {str(e)}", True

    def _should_review(self) -> bool:
        """判断是否需要对本次生成的图像进行审查"""
        is_group = getattr(self, "is_group", False)
        group_id = getattr(self, "group_id", "")
        user_id = getattr(self, "user_id", "")

        return ImageReviewer.should_review(
            is_group=is_group,
            group_id=group_id,
            user_id=user_id,
            config_getter=self.get_config,
        )

    async def _review_image(self, image_base64: str) -> Tuple[bool, str]:
        """审查图像是否违规

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
