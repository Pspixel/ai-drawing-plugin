"""AI 绘图插件配置定义"""
from src.plugin_system import ConfigField


# 配置节描述
CONFIG_SECTION_DESCRIPTIONS = {
    "plugin": "插件基本配置",
    "api": "Stable Diffusion API 配置",
    "generation": "图像生成参数配置",
    "bot": "机器人相关配置",
    "artist_styles": "画师风格配置",
    "image_review": "图像审查配置",
    "recall": "消息撤回配置",
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
            default="2.1.0",
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
        "default_additional_modules": ConfigField(
            type=list,
            default=[],
            description="默认外挂附加模块列表（VAE / Text Encoder），填写模块的 model_name，留空则不启用。可通过 /listmodules 命令查看可用模块",
            item_type="string",
            hint='填写模块文件名（model_name），例如：\ndefault_additional_modules = ["vae-ft-mse-840000-ema-pruned.safetensors", "clip_l.safetensors"]\n运行时可通过 /addmodule 和 /removemodule 命令动态增减',
        ),
        "available_upscalers": ConfigField(
            type=list,
            default=[],
            description="可用放大器列表（用于 /upscaler 命令切换时的备用列表，留空则从 SD API 实时拉取）",
            item_type="string",
        ),
    },
    "bot": {
        "appearance_description": ConfigField(
            type=str,
            default="a cute anime girl with blue hair and blue eyes, smiling, wearing a white dress",
            description="机器人的外观描述（用于自画像功能）",
        ),
    },
    "artist_styles": {
        "enabled": ConfigField(
            type=bool,
            default=False,
            description="是否启用画师风格功能（启用后用户可以在对话中指定使用哪个风格，未指定时不添加风格标签）",
        ),
        "styles": ConfigField(
            type=dict,
            default={
                "画师bakup": "naga u, (tyakomes:0.95), henreader, baku-p",
                "画师柚子社团": "Yuzusoft, Senren Banka",
                "画师混合A": "(naga u:1.1), (tyakomes:0.9), vibrant colors",
                "画师混合B": "Yuzusoft, (henreader:0.95), detailed",
            },
            description="画师风格标签配置（字典格式，键为中文风格名称，值为对应的英文 tag 串）。可以使用画师名称标签来指定特定画师的风格，注意：自动生成的 TOML 文件中，中文键名可能没有引号，需要手动添加双引号",
            hint='可以添加任意数量的风格。TOML 格式要求中文键名必须用双引号包裹:\n[artist_styles.styles]\n"画师bakup" = "naga u, (tyakomes:0.95), henreader, baku-p"\n"画师柚子社团" = "Yuzusoft, Senren Banka"\n"动漫风格" = "anime, colorful"\n\n如果自动生成的配置文件中键名没有引号（如 画师bakup = "..."），请手动添加双引号改为 "画师bakup" = "..."',
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
    "recall": {
        "auto_recall_enabled": ConfigField(
            type=bool,
            default=False,
            description="是否启用自动撤回功能（绘图后自动撤回图片消息）"
        ),
        "auto_recall_delay": ConfigField(
            type=int,
            default=60,
            description="自动撤回延迟时间（秒），默认 60 秒"
        ),
        "napcat_api_url": ConfigField(
            type=str,
            default="http://localhost:3000",
            description="NapCat HTTP API 地址",
            example="http://localhost:3000",
        ),
    },
}
