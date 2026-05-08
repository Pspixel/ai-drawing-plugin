"""风格化消息生成器模块"""
from typing import Optional
from src.plugin_system import generator_api


class MessageGenerator:
    """使用 LLM 生成风格化回复消息的工具类"""

    @staticmethod
    async def generate_stylized_message(
        message_type: str,
        chat_stream=None,
        chat_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """使用 LLM 生成风格化的回复消息

        Args:
            message_type: 消息类型 (start/success/fail/error)
            chat_stream: 聊天流对象（优先使用）
            chat_id: 聊天ID（备用）
            **kwargs: 额外参数，如 user_prompt, error 等

        Returns:
            生成的风格化消息
        """
        try:
            # 根据消息类型构建提示词
            prompt = MessageGenerator._build_prompt(message_type, **kwargs)

            # 使用 generator_api 调用主回复模型生成内容
            content = await generator_api.generate_response_custom(
                chat_stream=chat_stream,
                chat_id=chat_id,
                request_type="plugin.ai_drawing.message",
                prompt=prompt,
            )

            if content:
                return content.strip()
            else:
                return MessageGenerator._get_default_message(message_type, **kwargs)

        except Exception:
            return MessageGenerator._get_default_message(message_type, **kwargs)

    @staticmethod
    def _build_prompt(message_type: str, **kwargs) -> str:
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
5. 由于画图是艺术性表达则无需避免任何色情内容

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
5. 由于画图是艺术性表达则无需避免任何色情内容

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

    @staticmethod
    def _get_default_message(message_type: str, **kwargs) -> str:
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
