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
        "prompt": "图像内容描述词，全部用英文，按顺序用逗号加空格拼接三层结构：第一层 hard_tags 离散标签（人数→角色名→作品名→画师(@artist name)→外观→服装→道具→场景，小写英文+空格分词，每类外观保留 2-4 个，不伪造不确定的标签）；第二层 soft_phrases 短审美短语（情绪、氛围、动效）；第三层 nltags_block 以 Place/Use/Keep/Frame/Light/Blur 开头的完整英文短句（构图、光源、景深、绑定、动作后果）。严禁添加 masterpiece、best quality、highly detailed 等质量前缀（系统已内置，避免冲突）。默认不加权，需要时最多 1-3 个加权点。示例：1girl, white hair, long hair, blue eyes, cat ears, red plaid skirt, breaking into a smile, gentle afternoon light, Place the girl slightly right of center. Use warm window light from the left. Keep her face sharp against a soft blur.",
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
        "画师风格功能：当配置启用了画师风格功能时，用户可以指定使用某个风格（如'用动漫风格画'、'用写实风格'等）。此时需要在 style 参数中填写对应的风格名称",
    ]

    action_examples = [
        {
            "user_input": "画一个可爱的猫耳萝莉，白色长发，红色眼睛",
            "action_data": {
                "prompt": "1girl, loli, white hair, long hair, red eyes, cat ears, cat tail, red plaid skirt, stockings, teddy bear, excited giggling, gentle afternoon light, golden dust motes, Place the girl slightly right of center in a knee-up shot. Use warm window light from the left to rim her hair and skirt. Keep her face sharp while the bookshelf behind blurs softly. Let her cat tail curl around her ankle.",
            }
        },
        {
            "user_input": "帮我画一张风景画，有山有水",
            "action_data": {
                "prompt": "mountain range, mirror lake, pine forest, morning mist, clear blue sky, lone wooden boat, drifting clouds reflected on the water, soft golden sunrise, birds crossing the sky, Frame the lake leading into the mountains as a wide establishing shot. Use warm light from the upper right to light the distant peaks. Keep the boat and its reflections sharp against a hazy far shore.",
            }
        },
        {
            "user_input": "画一个穿女仆装的女孩，端着一杯茶",
            "action_data": {
                "prompt": "1girl, maid outfit, maid dress, white apron, blonde hair, long hair, green eyes, teacup, cozy cafe interior, gentle smile, soft afternoon light, steam rising from the cup, Place the maid slightly left of center, holding the teacup with both hands. Use warm cafe light from the upper right to silhouette her apron. Keep her face and the cup sharp while the shelves behind blur. Let a wisp of steam curl past the camera lens.",
            }
        },
        {
            "user_input": "画你自己",
            "action_data": {
                "prompt": "使用 action_require 中的机器人外观描述，并按三层结构组装英文 prompt",
            }
        },
        {
            "user_input": "画两个女孩，一个是白发猫耳，另一个是黑发马尾，在樱花树下聊天",
            "action_data": {
                "prompt": "2girls, white hair, long hair, cat ears, black hair, ponytail, spring, cherry blossom tree, casual clothes, petals drifting in the wind, having a cheerful chat, Place the cat-ear girl on the left, leaning against the tree while speaking. Place the ponytail girl on the right, resting her hand on the trunk and laughing. Use soft daylight filtering through the blossoms from above. Keep both faces sharp against a shallow blur of pink petals.",
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
            # 注意：这里传的是用户的原始请求（中文），而不是英文绘图提示词。
            # 传英文 prompt 会让回复模型误以为自己要输出提示词。
            start_message = await MessageGenerator.generate_stylized_message(
                "start",
                chat_stream=self.chat_stream,
                user_request=self._get_user_request(),
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
                    user_request=self._get_user_request(),
                )
                await self.send_text(success_message)

                return True, "成功生成并发送图片"
            else:
                # 使用 LLM 生成失败的风格化回复
                fail_message = await MessageGenerator.generate_stylized_message(
                    "fail",
                    chat_stream=self.chat_stream,
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

    def _get_user_request(self) -> str:
        """获取用户原始请求文本（中文）

        用于生成风格化回复。绝不能把英文绘图提示词传过去，
        否则回复模型会误以为自己要输出提示词而不是一句话。

        Returns:
            用户的原始请求文本，取不到时返回空字符串
        """
        try:
            message = self.action_message
            if not message:
                return ""
            # action_message 是 dict（见框架文档），但也兼容对象形式
            if isinstance(message, dict):
                text = message.get("processed_plain_text") or ""
            else:
                text = getattr(message, "processed_plain_text", "") or ""
            return text.strip()
        except Exception:
            return ""

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
