"""风格化消息生成器模块"""
import re
from typing import Optional

from src.plugin_system import generator_api

# 回复模型允许的最大字符数（含 emoji）
MAX_MESSAGE_LENGTH = 40

# 常见的多余前缀，模型有时会带上
_PREFIX_RE = re.compile(
    r"^\s*(?:回复|好的|好|输出|结果|改写后|改写后的回复|改写后的内容|消息|回答|回复如下)\s*[:：]\s*"
)

# 代码块
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")

# 是否包含中日韩字符
_CJK_RE = re.compile(r"[一-鿿぀-ヿ가-힯]")

# 句末标点，用于超长时截断
_SENTENCE_END_CHARS = "。！？!?～~…"


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
            **kwargs: 额外参数，如 user_request, user_prompt, error 等

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
                cleaned = MessageGenerator._clean_message(content)
                if cleaned:
                    return cleaned
            return MessageGenerator._get_default_message(message_type, **kwargs)

        except Exception:
            return MessageGenerator._get_default_message(message_type, **kwargs)

    @staticmethod
    def _build_prompt(message_type: str, **kwargs) -> str:
        """构建 LLM 提示词

        注意：这里给模型的角色是「聊天消息改写器」，不是绘图助手。
        绘图提示词（英文 tag）绝对不能出现在主题里，否则模型会误以为自己
        要输出提示词，而不是输出一句话。
        """
        # 用户原始请求（中文），没有则回退到旧的 user_prompt
        user_request = (kwargs.get("user_request") or kwargs.get("user_prompt") or "").strip()
        if len(user_request) > 120:
            user_request = user_request[:120] + "…"

        common_rules = """【你的角色】
你是一个「聊天消息改写器」。绘图插件已经在后台把图片画好了，你的工作只有一个：
把当前这个绘图状态，改写成一句像真人会发出来的简短中文消息。

【硬性规则】
1. 只输出最终的那一句话本身，不要输出任何其他内容。
2. 严禁输出英文单词、英文标签(tag)、逗号分隔的词表、代码块、markdown、编号列表。
3. 严禁输出提示词、tag、画面构图分析、光线建议、权重建议、画师风格讨论。
4. 严禁出现"我这边没法真正渲染出图""给你的是可以直接放进绘图工具的英文提示词"之类的说明——
   图片已经由绘图插件生成（或正在生成），你不需要也不允许解释绘图流程。
5. 严禁追问用户（不要问"需要我再调成宽幅或竖幅吗"这类问题）。
6. 严禁复述用户的请求原文，只表达你此刻的心情/状态。
7. 一句话，20~35 个字，可以带 1~2 个 emoji。
8. 直接输出这句话，不要加引号，不要加"回复："之类的前缀，不要加解释。"""

        if message_type == "start":
            topic = f"用户刚刚对你说：「{user_request}」，你正在给他画图。" if user_request else "用户刚刚请你画一张图，你正在给他画图。"
            return f"""{common_rules}

【当前情境】
{topic}

【输出示例】（照着这种口吻写，不要抄内容）
完成啦！快看看喜不喜欢~ 🎉
马上就好，等我一下~ ✨"""

        elif message_type == "success":
            topic = f"用户让你画的是「{user_request}」，图片已经画好并发送出去了。" if user_request else "图片已经画好并发送出去了。"
            return f"""{common_rules}

【当前情境】
{topic}

【输出示例】（照着这种口吻写，不要抄内容）
画好啦！快看看喜不喜欢~ 🎉
搞定！这次的创作我很满意呢~ 🌟"""

        elif message_type == "fail":
            return f"""{common_rules}

【当前情境】
这次图片生成失败了，你要跟用户说一声。

【输出示例】（照着这种口吻写，不要抄内容）
呜...这次没画出来呢，再试一次好不好~ 🥺"""

        elif message_type == "error":
            error = kwargs.get("error", "未知错误")
            return f"""{common_rules}

【当前情境】
生成图片时出了点问题（内部信息：{error}），你要跟用户说一声。
不要向用户暴露任何技术细节、报错信息或内部术语。

【输出示例】（照着这种口吻写，不要抄内容）
哎呀，出了点小状况...稍后再试试好吗~ 🥺"""

        return ""

    @staticmethod
    def _clean_message(content: str) -> str:
        """清洗模型输出：去掉代码块、多余段落与超长内容

        模型偶尔会不听话输出英文提示词/分析，这里做一道兜底。
        """
        if not content:
            return ""

        text = _CODE_BLOCK_RE.sub("", content)
        text = _INLINE_CODE_RE.sub("", text)

        # 逐行取第一句含中文的（能有效滤掉英文 tag 列表和纯参数行）
        picked = ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if _CJK_RE.search(line):
                picked = line
                break

        # 全篇都没有中文 -> 退而取第一行非空内容
        if not picked:
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if line:
                    picked = line
                    break

        if not picked:
            return ""

        # 去掉 "回复：" 之类的前缀和包裹的引号
        picked = _PREFIX_RE.sub("", picked)
        picked = picked.strip(" \t\"'“”‘’「」『』")

        # 超长则按句末标点截断
        if len(picked) > MAX_MESSAGE_LENGTH:
            cut_pos = -1
            for index, char in enumerate(picked[:MAX_MESSAGE_LENGTH]):
                if char in _SENTENCE_END_CHARS:
                    cut_pos = index
            if cut_pos >= 0:
                picked = picked[: cut_pos + 1]
            else:
                picked = picked[:MAX_MESSAGE_LENGTH].rstrip() + "…"

        return picked.strip()

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
