"""AI 绘图插件配置定义"""
from src.plugin_system import ConfigField


# 配置节描述
CONFIG_SECTION_DESCRIPTIONS = {
    "plugin": "插件基本配置",
    "api": "Stable Diffusion API 配置",
    "generation": "图像生成参数配置",
    "bot": "机器人相关配置",
}

# 配置 Schema
CONFIG_SCHEMA = {
    "plugin": {
        "enabled": ConfigField(
            type=bool,
            default=False,
            description="是否启用插件"
        ),
        "config_version": ConfigField(
            type=str,
            default="1.2.0",
            description="配置文件版本"
        ),
        "debug_mode": ConfigField(
            type=bool,
            default=False,
            description="调试模式（启用后会在聊天中显示详细的 prompt 信息）"
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
        "quality_prompt": ConfigField(
            type=str,
            default="masterpiece, best quality, highly detailed",
            description="质量提示词（只能在配置文件中修改，用于提升图像质量）",
        ),
        "content_prompt": ConfigField(
            type=str,
            default="",
            description="内容提示词（可由 Action/Command 组件动态设置，描述图像内容）",
        ),
        "negative_prompt": ConfigField(
            type=str,
            default="(nsfw:1.5), (nude:1.5), (explicit:1.5), lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
            description="默认负面提示词（使用权重语法如 (word:1.5) 可增强效果）",
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
        "hr_second_pass_steps": ConfigField(
            type=int,
            default=0,
            description="高分修复二次采样步数（0 表示与首次采样步数相同）",
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
