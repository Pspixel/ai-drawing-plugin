"""AI 绘图插件配置定义"""
from src.plugin_system import ConfigField


# 配置节描述
CONFIG_SECTION_DESCRIPTIONS = {
    "plugin": "插件基本配置",
    "api": "Stable Diffusion API 配置",
    "generation": "图像生成参数配置",
    "bot": "机器人相关配置",
    "image_review": "图像审查配置",
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
            default="2.0.1",
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
    "image_review": {
        "enabled": ConfigField(
            type=bool,
            default=False,
            description="是否启用图像审查功能"
        ),
        "vision_api_base_url": ConfigField(
            type=str,
            default="http://localhost:11434/v1",
            description="视觉模型 API 地址（OpenAI 兼容接口）",
            example="http://localhost:11434/v1",
        ),
        "vision_api_key": ConfigField(
            type=str,
            default="",
            description="视觉模型 API 密钥（本地部署可留空）",
            input_type="password",
        ),
        "vision_model_name": ConfigField(
            type=str,
            default="llava",
            description="视觉模型名称（如 llava、gpt-4o、qwen-vl-plus 等）",
            example="llava",
        ),
        "review_prompt": ConfigField(
            type=str,
            default=(
                "你是一个图像安全审查助手。请分析这张图片是否包含色情、裸露或违规内容。注意由于使用地在日本，根据日本的法律只要图中的角色没有直接裸露出生殖器,乳头，肛门等敏感部位则不算违规，穿着暴露或者仅仅只是挡住关键部分（例如三点式比基尼，创可贴贴住乳头等部位）并没有裸露的软色情不算做违规。"
                "请仅输出JSON格式的结果，不要输出其他任何内容。"
                'JSON格式如下：{"safe": true/false, "reason": "判断理由（简短描述）"}'
                "其中 safe 为 true 表示图片安全合规，false 表示图片违规。"
            ),
            description="图像审查的提示词（发送给视觉模型用于判断图片是否违规）",
            input_type="textarea",
            rows=4,
        ),
        "block_message": ConfigField(
            type=str,
            default="⚠️ 生成的图片未通过安全审查，已拦截输出。",
            description="图片违规时的拦截提示消息",
        ),
        "review_error_message": ConfigField(
            type=str,
            default="⚠️ 图像审查服务异常，为安全起见已拦截输出。",
            description="图像审查服务异常时的提示消息",
        ),
        "private_mode": ConfigField(
            type=str,
            default="whitelist",
            description="私聊审查模式: whitelist(白名单模式，名单内不审查直接输出) / blacklist(黑名单模式，名单外直接输出)",
            example="whitelist",
        ),
        "private_ids": ConfigField(
            type=list,
            default=[],
            description='私聊黑白名单用户ID列表（配合 private_mode 使用）。TOML 示例: private_ids = ["123456789", "987654321"]',
            item_type="string",
            hint="建议填写字符串类型（带引号），如 ['123456789']。白名单模式: 名单内用户不审查直接输出; 黑名单模式: 名单内用户需要审查",
        ),
        "group_mode": ConfigField(
            type=str,
            default="whitelist",
            description="群聊审查模式: whitelist(白名单模式，名单内不审查直接输出) / blacklist(黑名单模式，名单外直接输出)",
            example="whitelist",
        ),
        "group_ids": ConfigField(
            type=list,
            default=[],
            description='群聊黑白名单群ID列表（配合 group_mode 使用）。TOML 示例: group_ids = ["123456789", "987654321"]',
            item_type="string",
            hint="建议填写字符串类型（带引号），如 ['123456789']。白名单模式: 名单内群不审查直接输出; 黑名单模式: 名单内群需要审查",
        ),
    },
}
