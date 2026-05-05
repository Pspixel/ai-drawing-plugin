"""图像审查模块 - 使用视觉模型判断图像是否色情违规"""
import json
import aiohttp
from typing import Optional, Tuple


class ImageReviewer:
    """图像审查器，通过视觉模型API判断图像是否违规"""

    @staticmethod
    async def review_image(
        image_base64: str,
        api_base_url: str,
        api_key: str,
        model_name: str,
        review_prompt: str,
    ) -> Tuple[bool, Optional[str]]:
        """调用视觉模型审查图像是否违规

        使用 OpenAI 兼容的多模态聊天接口发送图片给视觉模型，
        解析模型返回的 JSON 结果判断是否合规。

        Args:
            image_base64: 图片的 base64 编码（无头，即不含 data:image/... 前缀）
            api_base_url: 视觉模型 API 地址（如 http://localhost:11434/v1）
            api_key: API 密钥（可为空字符串）
            model_name: 视觉模型名称（如 gpt-4o、qwen-vl-plus 等）
            review_prompt: 审查用的提示词

        Returns:
            Tuple[bool, Optional[str]]:
                - 第一个 bool: True 表示图片安全合规，False 表示违规
                - 第二个值: 违规原因（合规时为 None）
        """
        try:
            # 构建多模态消息（OpenAI 兼容格式）
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": review_prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                            },
                        },
                    ],
                }
            ]

            # 构建请求
            url = f"{api_base_url.rstrip('/')}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": 200,
                "temperature": 0.1,
            }

            # 发送请求
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"[图像审查] API 请求失败 {response.status}: {error_text[:200]}")
                        return False, "审查服务请求失败"

                    result = await response.json()
                    content = result["choices"][0]["message"]["content"].strip()

            # 解析 JSON 结果
            return ImageReviewer._parse_review_result(content)

        except KeyError as e:
            print(f"[图像审查] 响应格式异常: {e}")
            return False, "审查响应格式异常"
        except aiohttp.ClientError as e:
            print(f"[图像审查] 网络请求错误: {e}")
            return False, "审查服务网络错误"
        except Exception as e:
            print(f"[图像审查] 审查过程出错: {e}")
            return False, f"审查异常: {str(e)}"

    @staticmethod
    def _parse_review_result(content: str) -> Tuple[bool, Optional[str]]:
        """解析视觉模型返回的审查结果

        尝试从返回文本中提取 JSON，支持模型可能返回的
        markdown 代码块包裹等格式。

        Args:
            content: 视觉模型返回的原始文本

        Returns:
            Tuple[bool, Optional[str]]: (是否合规, 违规原因)
        """
        # 尝试提取 JSON 内容
        json_str = content

        # 处理 markdown 代码块包裹的情况
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        # 尝试找到 JSON 对象的边界
        start = json_str.find("{")
        end = json_str.rfind("}") + 1
        if start != -1 and end > start:
            json_str = json_str[start:end]
        else:
            print(f"[图像审查] 未能从返回内容中提取 JSON: {content[:200]}")
            return False, "审查结果格式异常"

        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[图像审查] JSON 解析失败: {e}, 原始内容: {json_str[:200]}")
            return False, "审查结果解析失败"

        is_safe = result.get("safe", True)
        reason = result.get("reason", None)

        if is_safe:
            return True, None
        else:
            return False, reason or "图片内容违规"

    @staticmethod
    def _match_id(target_id, id_list: list) -> bool:
        """匹配 ID，兼容字符串和整数类型

        TOML 中数字列表会被解析为 int，而 group_id/user_id 通常是 str，
        因此需要统一转换为字符串进行比较。

        Args:
            target_id: 待匹配的ID（通常为字符串）
            id_list: ID列表（可能包含 int 或 str）

        Returns:
            bool: 是否匹配
        """
        target_str = str(target_id)
        return any(str(item) == target_str for item in id_list)

    @staticmethod
    def should_review(
        is_group: bool,
        group_id: str,
        user_id: str,
        config_getter,
    ) -> bool:
        """根据黑白名单配置判断是否需要对本次生成的图像进行审查

        逻辑说明：
        - 审查总开关未开启 → 不审查任何图像，直接发送
        - 审查总开关开启 → 由黑白名单决定谁来审查
          - 白名单模式：仅白名单中的用户/群审查，其余不审查
          - 黑名单模式：仅黑名单中的用户/群审查，其余不审查
          - 白名单+黑名单同时启用：优先检查白名单，命中则审查；
            未命中白名单再检查黑名单，命中则审查；都不命中则不审查
          - 黑白名单都未启用 → 不审查任何图像（相当于只开了总开关但没配置名单）

        Args:
            is_group: 是否为群聊
            group_id: 群ID（私聊时可为空字符串）
            user_id: 用户ID
            config_getter: 获取配置的回调函数，签名: (key, default) -> value

        Returns:
            bool: True 表示需要审查，False 表示不需要审查
        """
        # 检查图像审查总开关
        review_enabled = config_getter("image_review.enabled", False)
        if not review_enabled:
            return False

        if is_group:
            # 群聊场景
            # 检查白名单：白名单中的群需要审查
            group_whitelist_enabled = config_getter("group_whitelist.enabled", False)
            if group_whitelist_enabled:
                group_whitelist = config_getter("group_whitelist.group_ids", [])
                if ImageReviewer._match_id(group_id, group_whitelist):
                    return True  # 白名单命中，需要审查

            # 检查黑名单：黑名单中的群需要审查
            group_blacklist_enabled = config_getter("group_blacklist.enabled", False)
            if group_blacklist_enabled:
                group_blacklist = config_getter("group_blacklist.group_ids", [])
                if ImageReviewer._match_id(group_id, group_blacklist):
                    return True  # 黑名单命中，需要审查

            # 不在任何名单中，不审查
            return False
        else:
            # 私聊场景
            # 检查白名单：白名单中的用户需要审查
            private_whitelist_enabled = config_getter("private_whitelist.enabled", False)
            if private_whitelist_enabled:
                private_whitelist = config_getter("private_whitelist.user_ids", [])
                if ImageReviewer._match_id(user_id, private_whitelist):
                    return True  # 白名单命中，需要审查

            # 检查黑名单：黑名单中的用户需要审查
            private_blacklist_enabled = config_getter("private_blacklist.enabled", False)
            if private_blacklist_enabled:
                private_blacklist = config_getter("private_blacklist.user_ids", [])
                if ImageReviewer._match_id(user_id, private_blacklist):
                    return True  # 黑名单命中，需要审查

            # 不在任何名单中，不审查
            return False
