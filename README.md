# 🎨 AI 绘图插件

基于 Stable Diffusion WebUI API 的 AI 绘图插件，为 MaiBot 提供强大的图像生成能力。

## ✨ 功能特性

- 🤖 **智能绘图 (Action)**: 机器人可以根据对话上下文智能判断何时生成图片
- 💻 **命令绘图 (Command)**: 通过命令直接生成图片
- 🔄 **模型管理**: 查看和切换 Stable Diffusion 模型
- ⚙️ **灵活配置**: 支持丰富的参数配置，包括分辨率、采样器、高分修复等
- 🖼️ **自画像功能**: 机器人可以根据配置的外观描述生成自己的画像
- 💬 **风格化回复**: 使用 LLM 生成活泼可爱的个性化回复消息
- 🛡️ **图像审查**: 支持通过视觉模型对生成的图像进行内容审查，可配置名单模式（白名单/黑名单）

## 📦 依赖要求

- Python 3.8+
- aiohttp
- Stable Diffusion WebUI (需要启动 API 模式)

## 🚀 快速开始

### 1. 启动 Stable Diffusion WebUI

确保你的 Stable Diffusion WebUI 已启动并开启了 API 功能：

拿绘世启动器举例，点开启动器左边的**高级选项**，找到**网络设置**部分的**启用api**选项即可。

默认 API 地址为 `http://localhost:7860`

### 2. 安装插件

将插件目录放置到 MaiBot 的 `plugins/` 目录下：

```
plugins/
└── ai_drawing_plugin/
    ├── _manifest.json
    ├── plugin.py
    ├── sd_client.py
    └── README.md
```

### 3. 配置插件

首次启动 MaiBot 后，插件会自动生成配置文件 `config.toml`。

编辑配置文件以启用插件并调整参数：

```toml
[plugin]
enabled = true  # 启用插件

[api]
base_url = "http://localhost:7860"  # 修改为你的 SD WebUI 地址

[generation]
width = 512
height = 512
steps = 20
enable_hr = false  # 是否启用高分修复

[bot]
appearance_description = "a cute anime girl with blue hair"  # 机器人外观描述
```

### 4. 重启 MaiBot

重启后插件即可生效。

## 📖 使用方法

### 智能绘图 (Action)

机器人会根据对话内容智能判断是否需要生成图片：

```
用户: 帮我画一张美丽的风景画
机器人: 正在为你生成图片，请稍等...
机器人: [发送生成的图片]
机器人: 图片生成完成！
```

```
用户: 画一张你的自画像
机器人: 正在为你生成图片，请稍等...
机器人: [根据配置的外观描述生成图片]
```

### 命令绘图 (Command)

#### `/draw <描述>` - 生成图片

```
/draw a beautiful sunset over the ocean
```

#### `/drawhelp` - 查看帮助

```
/drawhelp
```

显示所有可用命令和使用说明。

#### `/drawmodel` - 查看当前模型

```
/drawmodel
```

显示当前使用的 Stable Diffusion 模型。

#### `/switchmodel [模型名]` - 查看或切换模型

```
/switchmodel                           # 列出可选模型和当前模型
/switchmodel anime_model.safetensors   # 切换到指定模型
```

不带参数时列出 SD WebUI 中所有可用模型，带参数时切换到指定模型（支持模糊匹配）。

#### `/sampler [采样器名]` - 查看或切换采样器

```
/sampler                    # 查看可用采样器列表
/sampler DPM++ 2M Karras   # 切换到指定采样器
```

查看可用的采样器列表或切换到指定采样器。

#### `/scheduler [调度器名]` - 查看或切换调度器

```
/scheduler           # 查看可用调度器列表
/scheduler Karras    # 切换到指定调度器
```

查看可用的调度器列表或切换到指定调度器。

## ⚙️ 配置说明

### API 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api.base_url` | string | `http://localhost:7860` | Stable Diffusion WebUI API 地址 |

### 生成参数配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `generation.default_prompt` | string | `masterpiece, best quality...` | 默认正面提示词 |
| `generation.negative_prompt` | string | `lowres, bad anatomy...` | 默认负面提示词 |
| `generation.width` | int | `512` | 图像宽度（像素） |
| `generation.height` | int | `512` | 图像高度（像素） |
| `generation.steps` | int | `20` | 采样步数 |
| `generation.cfg_scale` | float | `7.0` | 提示词相关性 |
| `generation.sampler_name` | string | `Euler a` | 采样器名称 |
| `generation.scheduler` | string | `""` | 调度器类型 |
| `generation.enable_hr` | bool | `false` | 是否启用高分修复 |
| `generation.hr_scale` | float | `2.0` | 高分修复放大倍数 |
| `generation.hr_upscaler` | string | `Latent` | 高分修复放大器 |
| `generation.denoising_strength` | float | `0.7` | 去噪强度 |
| `generation.available_samplers` | list | `["Euler a", ...]` | 可用的采样器列表 |
| `generation.available_schedulers` | list | `["Automatic", ...]` | 可用的调度器列表 |

### 机器人配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `bot.appearance_description` | string | `a cute anime girl...` | 机器人外观描述（用于自画像） |

### 图像审查配置

插件支持通过视觉模型（如 LLaVA、GPT-4o 等）对生成的图像进行内容审查，可通过名单模式灵活控制审查范围。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `image_review.enabled` | bool | `false` | 是否启用图像审查功能 |
| `image_review.vision_api_base_url` | string | `http://localhost:11434/v1` | 视觉模型 API 地址（OpenAI 兼容格式） |
| `image_review.vision_api_key` | string | `""` | API 密钥（本地部署可留空） |
| `image_review.vision_model_name` | string | `llava` | 视觉模型名称 |
| `image_review.review_prompt` | string | `你是一个图像安全审查助手...` | 审查提示词（要求模型返回 JSON 格式） |
| `image_review.block_message` | string | `⚠️ 生成的图片未通过安全审查...` | 图片违规时的拦截提示消息 |
| `image_review.review_error_message` | string | `⚠️ 图像审查服务异常...` | 审查服务异常时的提示消息 |
| `image_review.private_mode` | string | `whitelist` | 私聊审查模式：`whitelist`（白名单）/ `blacklist`（黑名单） |
| `image_review.private_ids` | list | `[]` | 私聊名单用户ID列表 |
| `image_review.group_mode` | string | `whitelist` | 群聊审查模式：`whitelist`（白名单）/ `blacklist`（黑名单） |
| `image_review.group_ids` | list | `[]` | 群聊名单群ID列表 |

**名单模式逻辑说明：**
- 审查总开关关闭 → 不审查任何图像，直接发送
- 审查总开关开启 → 由名单模式决定审查范围
  - **白名单模式**（默认）：名单中的用户/群直接放行（不审查），其余需要审查
  - **黑名单模式**：名单中的用户/群需要审查，其余直接放行（不审查）

#### 配置示例

```toml
[image_review]
enabled = true
vision_api_base_url = "http://127.0.0.1:11434/v1"
vision_api_key = ""
vision_model_name = "llava"

# 群聊使用黑名单模式：名单中的群需要审查，其余直接放行
group_mode = "blacklist"
group_ids = ["123456789", "987654321"]

# 私聊使用白名单模式（默认）：名单中的用户直接放行，其余需要审查
private_mode = "whitelist"
private_ids = ["10001", "10002"]
```

## 🎯 Action 组件说明

### AIDrawingAction

智能绘图动作，机器人会根据对话上下文自动判断是否使用。

**激活条件**: 始终激活 (ALWAYS)

**使用场景**:
- 用户明确要求生成图片、绘画、画图
- 用户描述了想要的图像内容
- 用户要求画机器人的自画像

**参数**:
- `prompt`: 图像描述词（必需）
- `width`: 图像宽度（可选）
- `height`: 图像高度（可选）
- `enable_hr`: 是否启用高分修复（可选）

## 💻 Command 组件说明

### DrawCommand

直接绘图命令，用户可以通过命令立即生成图片。

**命令格式**: `/draw <描述>`

### DrawHelpCommand

显示帮助信息。

**命令格式**: `/drawhelp`

### CurrentModelCommand

查看当前使用的模型。

**命令格式**: `/drawmodel`

### SwitchModelCommand

查看可选模型列表或切换 Stable Diffusion 模型。模型列表从 SD WebUI API 实时获取。

**命令格式**:
- `/switchmodel` - 列出可选模型和当前模型
- `/switchmodel <模型名>` - 切换到指定模型

### SwitchSamplerCommand

查看或切换采样器。

**命令格式**:
- `/sampler` - 查看可用采样器列表
- `/sampler <采样器名>` - 切换到指定采样器

### SwitchSchedulerCommand

查看或切换调度器。

**命令格式**:
- `/scheduler` - 查看可用调度器列表
- `/scheduler <调度器名>` - 切换到指定调度器

## 🔧 高级用法

### 风格化回复

插件会自动使用 LLM API 生成活泼可爱的个性化回复消息，包括：
- 开始生成时的期待消息
- 生成成功时的欢快消息
- 生成失败时的安慰消息
- 出错时的温柔提示

如果 LLM API 不可用，会自动降级到默认的简单文本回复。

### 自定义采样器

在配置文件中修改 `sampler_name`：

```toml
[generation]
sampler_name = "DPM++ 2M Karras"
```

常用采样器：
- `Euler a` - 快速，适合初次尝试
- `DPM++ 2M Karras` - 质量好，速度适中（推荐）
- `DPM++ SDE Karras` - 质量最好，速度较慢

### 启用高分修复

高分修复可以生成更高分辨率的图片：

```toml
[generation]
enable_hr = true
hr_scale = 2.0  # 放大倍数
hr_upscaler = "R-ESRGAN 4x+"  # 放大器
```

### 调整图像质量

通过调整 `steps` 和 `cfg_scale` 来平衡质量和速度：

```toml
[generation]
steps = 30  # 增加步数提高质量（但会变慢）
cfg_scale = 7.5  # 提高相关性使图像更符合提示词
```

## 🐛 常见问题

### Q: 提示"图片生成失败"

**A**: 检查以下几点：
1. Stable Diffusion WebUI 是否正常运行
2. API 地址配置是否正确
3. 查看 SD WebUI 的控制台是否有错误信息

### Q: 生成速度很慢

**A**: 可以尝试：
1. 减少 `steps` 参数（如改为 15-20）
2. 降低图像分辨率（如 512x512）
3. 关闭高分修复 (`enable_hr = false`)

### Q: 如何查看可用的模型列表？

**A**: 直接使用 `/switchmodel` 命令（无需参数）即可查看 SD WebUI 中所有可用的模型。

### Q: 切换模型后没有生效

**A**: 模型切换需要一定时间加载，请等待几秒后再尝试生成图片。

## 📝 开发说明

### 文件结构

```
ai_drawing_plugin/
├── _manifest.json      # 插件元数据
├── plugin.py           # 插件主文件（Action 和 Command）
├── sd_client.py        # Stable Diffusion API 客户端
└── README.md           # 说明文档
```

### 扩展功能

你可以基于此插件扩展更多功能：

1. **图生图功能**: 在 `sd_client.py` 中添加 `img2img` 方法
2. **批量生成**: 修改 `batch_size` 参数
3. **LoRA 支持**: 在 prompt 中添加 LoRA 标签
4. **进度查询**: 使用 `/sdapi/v1/progress` API 显示生成进度

## 📄 许可证

本插件遵循 AGPL-3.0 许可证。

## 🙏 致谢

- [Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
- [MaiBot](https://github.com/Maim-with-u/MaiBot)

## 📮 反馈与支持

如有问题或建议，欢迎提交 Issue。
