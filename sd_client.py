"""Stable Diffusion WebUI API 客户端"""
import aiohttp
import base64
from typing import Optional, Dict, Any, List, Tuple
from io import BytesIO


class StableDiffusionClient:
    """Stable Diffusion WebUI API 客户端"""

    def __init__(self, base_url: str = "http://localhost:7860"):
        """初始化客户端

        Args:
            base_url: Stable Diffusion WebUI 的基础 URL
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时

    async def txt2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg_scale: float = 7.0,
        sampler_name: str = "Euler a",
        scheduler: Optional[str] = None,
        enable_hr: bool = False,
        hr_scale: float = 2.0,
        hr_upscaler: str = "Latent",
        hr_second_pass_steps: int = 0,
        denoising_strength: float = 0.7,
        hr_additional_modules: list = None,
        seed: int = -1,
        batch_size: int = 1,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """文生图 API

        Args:
            prompt: 正面提示词
            negative_prompt: 负面提示词
            width: 图像宽度
            height: 图像高度
            steps: 采样步数
            cfg_scale: 提示词相关性
            sampler_name: 采样器名称
            scheduler: 调度器类型
            enable_hr: 是否启用高清修复
            hr_scale: 高清放大倍数
            hr_upscaler: 高清放大器名称
            hr_second_pass_steps: 高清修复二次采样步数（0 表示与首次相同）
            denoising_strength: 去噪强度
            hr_additional_modules: 高清修复阶段的附加网络模块列表（Forge 专用，默认 ["Use same choices"]）
            seed: 随机种子
            batch_size: 批次大小
            **kwargs: 其他参数

        Returns:
            包含生成图像的响应字典，失败返回 None
        """
        url = f"{self.base_url}/sdapi/v1/txt2img"

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler_name,
            "seed": seed,
            "batch_size": batch_size,
            "enable_hr": enable_hr,
        }

        # 添加调度器参数
        # 注意: 空字符串表示使用默认调度器，None 表示不指定
        if scheduler is not None and scheduler != "":
            payload["scheduler"] = scheduler
        elif scheduler == "":
            # 空字符串时使用 "Automatic"（WebUI 的默认值）
            payload["scheduler"] = "Automatic"

        # 添加高清修复参数
        if enable_hr:
            payload["hr_scale"] = hr_scale
            payload["hr_upscaler"] = hr_upscaler
            payload["hr_second_pass_steps"] = hr_second_pass_steps
            payload["denoising_strength"] = denoising_strength
            # 修复 Forge 的 hr_additional_modules 为 None 导致的 TypeError
            # 参见: Forge processing.py line 1405
            # 'Use same choices' not in self.hr_additional_modules
            # 当通过 API 调用且未传此字段时，Forge 会将其反序列化为 None
            payload["hr_additional_modules"] = hr_additional_modules if hr_additional_modules is not None else ["Use same choices"]

        # 添加其他参数
        payload.update(kwargs)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        print(f"API 错误 {response.status}: {error_text}")
                        return None
        except aiohttp.ClientError as e:
            print(f"网络请求错误: {e}")
            return None
        except Exception as e:
            print(f"未知错误: {e}")
            return None

    async def get_models(self) -> Optional[List[Dict[str, Any]]]:
        """获取可用模型列表

        Returns:
            模型列表，失败返回 None
        """
        url = f"{self.base_url}/sdapi/v1/sd-models"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
        except Exception as e:
            print(f"获取模型列表失败: {e}")
            return None

    async def get_current_model(self) -> Optional[str]:
        """获取当前使用的模型

        Returns:
            当前模型名称，失败返回 None
        """
        url = f"{self.base_url}/sdapi/v1/options"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        options = await response.json()
                        return options.get("sd_model_checkpoint")
                    else:
                        return None
        except Exception as e:
            print(f"获取当前模型失败: {e}")
            return None

    async def switch_model(self, model_title: str) -> Tuple[bool, str]:
        """切换模型

        Args:
            model_title: SD API 返回的模型 title（如 "model.safetensors [abc123]"）

        Returns:
            (是否成功, 错误信息)
        """
        url = f"{self.base_url}/sdapi/v1/options"

        payload = {
            "sd_model_checkpoint": model_title
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        return True, ""
                    else:
                        error_text = await response.text()
                        return False, f"API 返回 {response.status}: {error_text[:200]}"
        except Exception as e:
            print(f"切换模型失败: {e}")
            return False, str(e)

    async def find_model(self, query: str) -> Optional[Dict[str, Any]]:
        """根据用户输入匹配模型

        按优先级匹配: title 精确 > model_name 精确 > 模糊包含匹配

        Args:
            query: 用户输入的模型名（可以是 title、model_name 或部分名称）

        Returns:
            匹配到的模型字典，未找到返回 None
        """
        models = await self.get_models()
        if not models:
            return None

        # 精确匹配 title
        for m in models:
            if query == m.get("title", ""):
                return m

        # 精确匹配 model_name
        for m in models:
            if query == m.get("model_name", ""):
                return m

        # 匹配 title 去掉 hash 后缀（如 "model.safetensors [abc123]" -> "model.safetensors"）
        for m in models:
            title = m.get("title", "")
            title_without_hash = title.split(" [")[0] if " [" in title else title
            if query == title_without_hash:
                return m

        # 模糊匹配（包含关系）
        query_lower = query.lower()
        for m in models:
            title = m.get("title", "")
            model_name = m.get("model_name", "")
            if query_lower in title.lower() or query_lower in model_name.lower():
                return m

        return None

    def format_model_list(self, models: List[Dict[str, Any]], current_title: Optional[str] = None) -> str:
        """格式化模型列表用于显示

        Args:
            models: SD API 返回的模型列表
            current_title: 当前模型的 title

        Returns:
            格式化的模型列表字符串
        """
        lines = []
        for i, m in enumerate(models):
            title = m.get("title", "未知")
            model_name = m.get("model_name", "")
            is_current = current_title and title == current_title
            prefix = "→" if is_current else " "
            # 截断过长的 hash
            line = f"{prefix} {title}"
            lines.append(line)
        return "\n".join(lines)

    async def get_modules(self) -> Optional[List[Dict[str, Any]]]:
        """获取可用附加模块列表（VAE / Text Encoder）

        仅 SD-Forge 支持此端点。

        Returns:
            模块列表，每项包含 model_name 和 filename 字段，失败返回 None
        """
        url = f"{self.base_url}/sdapi/v1/sd-modules"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
        except Exception as e:
            print(f"获取模块列表失败: {e}")
            return None

    async def get_samplers(self) -> Optional[List[Dict[str, Any]]]:
        """获取可用采样器列表

        Returns:
            采样器列表，失败返回 None
        """
        url = f"{self.base_url}/sdapi/v1/samplers"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
        except Exception as e:
            print(f"获取采样器列表失败: {e}")
            return None

    async def get_schedulers(self) -> Optional[List[Dict[str, Any]]]:
        """获取可用调度器列表

        Returns:
            调度器列表，失败返回 None
        """
        url = f"{self.base_url}/sdapi/v1/schedulers"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
        except Exception as e:
            print(f"获取调度器列表失败: {e}")
            return None

    @staticmethod
    def decode_base64_image(base64_str: str) -> bytes:
        """解码 Base64 图像

        Args:
            base64_str: Base64 编码的图像字符串

        Returns:
            图像字节数据
        """
        return base64.b64decode(base64_str)
