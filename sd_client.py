"""Stable Diffusion WebUI API 客户端"""
import aiohttp
import base64
from typing import Optional, Dict, Any, List
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
        denoising_strength: float = 0.7,
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
            denoising_strength: 去噪强度
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
            payload["denoising_strength"] = denoising_strength

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

    async def switch_model(self, model_name: str) -> bool:
        """切换模型

        Args:
            model_name: 模型名称

        Returns:
            是否切换成功
        """
        url = f"{self.base_url}/sdapi/v1/options"

        payload = {
            "sd_model_checkpoint": model_name
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload) as response:
                    return response.status == 200
        except Exception as e:
            print(f"切换模型失败: {e}")
            return False

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
