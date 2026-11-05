# 🎨 AI 绘图插件

基于 Stable Diffusion WebUI API 的 AI 绘图插件，为 MaiBot 提供强大的图像生成能力。

## 📚 文档导航

项目说明文档集中在 `docs/`，README 提供安装、使用与开发入口：

- [配置文件修复指南](docs/CONFIG_FIX_GUIDE.md) - 修复 TOML 中文键名格式
- [图像审查功能指南](docs/NSFW_FILTER_GUIDE.md) - 图像审查与名单配置
- [项目结构说明](docs/STRUCTURE.md) - 模块职责与扩展方式
- [角色标签智能检索](docs/TAG_RETRIEVAL_GUIDE.md) - Tool 配置、索引缓存、降级策略与部署验收
- [配置定义](config.py) - 全部配置字段与默认值，运行配置由 MaiBot 自动生成

## ✨ 功能特性

- 🤖 **智能绘图 (Action)**: 机器人可以根据对话上下文智能判断何时生成图片
- 🔎 **角色标签工具 (Tool)**: 角色向量召回、混合候选重排，绘图规划前获取角色触发词与外观事实
- 💻 **命令绘图 (Command)**: 通过命令直接生成图片
- 🔄 **模型管理**: 查看和切换 Stable Diffusion 模型
- 🧩 **附加模块管理**: 动态加载外挂 VAE / Text Encoder（SD-Forge 专用）
- ⚙️ **灵活配置**: 支持丰富的参数配置，包括分辨率、采样器、高分修复等
- 🖼️ **自画像功能**: 机器人可以根据配置的外观描述生成自己的画像
- 🎨 **多风格支持**: 支持配置多个画师风格的 tag 组合，用户可在对话中指定使用哪个风格
- 💬 **风格化回复**: 使用 LLM 生成活泼可爱的个性化回复消息
- 🛡️ **图像审查**: 支持通过视觉模型对生成的图像进行内容审查，可配置名单模式（白名单/黑名单）

## 📦 依赖要求

- Python 3.10+（同时满足所用 MaiBot 版本要求）
- aiohttp
- numpy
- Stable Diffusion WebUI (需要启动 API 模式)

## 🚀 快速开始

### 1. 启动 Stable Diffusion WebUI

确保你的 Stable Diffusion WebUI 已启动并开启了 API 功能：

拿绘世启动器举例，点开启动器左边的**高级选项**，找到**网络设置**部分的**启用api**选项即可。

默认 API 地址为 `http://localhost:7860`

### 2. 安装插件

将完整插件目录放置到 MaiBot 的 `plugins/` 目录下，保留各模块目录：

```text
MaiBot/
└── plugins/
    └── ai_drawing_plugin/    # 本仓库完整内容，结构见下方“开发说明”
```

在 MaiBot 使用的 Python 环境中安装插件依赖：

```powershell
python -m pip install aiohttp numpy
```

### 3. 配置插件

首次启动 MaiBot 后，插件会自动生成配置文件 `config.toml`。

全部配置字段与默认值见 [config.py](config.py)，专项配置示例见 `docs/` 中的对应指南。

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

```
用户: 用动漫风格画一个可爱的猫耳娘
机器人: 正在为你生成图片，请稍等...
机器人: [使用动漫风格的 tag 组合生成图片]
```

命名角色的智能绘图可先调用 `character_tag_lookup`，通过 SQLite 名称匹配、向量召回与重排获得标签事实。配置与规划前桥接说明见 [角色标签智能检索](docs/TAG_RETRIEVAL_GUIDE.md)。API 密钥留空时只查询 SQLite；现有 `/chartag` 查询行为保持不变。

#### 角色标签索引与缓存

角色检索采用“首次全库向量化、本地缓存、后续只向量化查询词”的方式：

- **首次构建**：配置有效的检索 API 密钥后，插件启动时会检查索引缓存。没有有效缓存时，从 `data/character_tags.db` 读取角色名、英文标识、作品、触发词和核心标签，分批发送到 Embedding API。以 36,495 个角色、默认每批 32 条计算，需要约 1,141 个串行请求，首次构建可能耗时较长。
- **本地保存**：全部批次成功后，将向量和校验元数据保存到 `data/character_vectors.npz`。SQLite 保存原始角色数据，向量单独保存在该文件中；插件不附带预先生成的向量索引。
- **后续查询**：只将本次角色名及可选作品名发送到 Embedding API，再用查询向量在本地缓存中计算相似度。随后将向量召回和名称匹配得到的少量候选发送到 Rerank API，默认最多约 60 条，最终返回最多 3 条；每次查询不会重新向量化整个角色库。
- **缓存复用与重建**：重启时按数据库内容指纹、Embedding 模型 ID 和接口地址校验缓存，有效则直接加载。缓存缺失、损坏或校验不一致时才重新构建全库索引。

首次构建期间发起角色检索，会等待索引完成后再继续绘图规划。当前没有逐批进度日志，因此可能出现日志长时间没有更新的情况；构建完成后会输出“角色向量索引就绪，记录数：…”日志。`tag_retrieval.timeout` 只限制单次接口请求，不是全库构建的总时限。

当前索引在全部批次成功后才保存，不支持断点续传；如果首次构建失败或中途重启，后续构建可能从头开始。构建失败时当前查询会降级为 SQLite 名称查询。

### 命令绘图 (Command)

#### `/draw <描述>` - 生成图片

```
/draw a beautiful sunset over the ocean
```

#### `/chartag <角色名>[,作品名]` - 查询角色绘图标签

```
/chartag 甘雨           # 按角色名模糊查询
/chartag 甘雨,原神      # 同时按角色名和作品名模糊查询（中英文逗号均可）
```

别名：`/查角色`、`/角色标签`。从本地角色库 `data/character_tags.db` 中查询，以合并转发消息返回每个角色的缩略图、触发标签和核心标签，按记录热度（count）降序排列。角色数据库和 `thumbs/` 缩略图需在部署时准备，均不随 Git 提交。

> **角色查询资源状态**：角色数据库、向量索引和角色图片均属于较大的本地二进制资源，当前暂未上传到 GitHub，后续会补充。需要使用角色标签查询时，请准备以下文件或目录：
>
> - `data/character_tags.db`：`/chartag` 查询和角色名称匹配所需的 SQLite 数据库。
> - `data/character_vectors.npz`：语义检索使用的本地向量索引。配置有效的 Embedding API 密钥后，插件也可以根据角色数据库首次构建该索引；没有索引时会先降级为 SQLite 查询。
> - `thumbs/`：角色缩略图目录。图片缺失时仍可返回文字标签，但不会显示对应缩略图。
>
> 在这些资源补充前，仓库中的代码和测试可以正常使用，但真实角色数据查询和带图片的结果展示无法完整工作。

- 超出 `character_query.max_results`（默认 20）时只显示前 N 个，可用“角色名,作品名”缩小范围
- 缩略图缺失的角色只返回文本；合并转发发送失败时自动降级为逐条发送
- 注意：MaiBot 发送合并转发前会对其中每张图片调用一次识图（VLM），`storage_message=False` 也无法避免，因此不建议把 `max_results` 调得过大

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
/sampler                    # 从 SD API 实时拉取采样器列表
/sampler DPM++ 2M Karras   # 切换到指定采样器
```

从 SD WebUI API 实时获取可用采样器列表，或切换到指定采样器。切换后重启前一直生效。

#### `/scheduler [调度器名]` - 查看或切换调度器

```
/scheduler           # 从 SD API 实时拉取调度器列表
/scheduler karras    # 切换到指定调度器（使用括号内的传参名）
```

从 SD WebUI API 实时获取可用调度器列表，或切换到指定调度器。列表中会同时显示显示名和传参名。

#### `/upscaler [放大器名]` - 查看或切换高分修复放大器

```
/upscaler                    # 从 SD API 实时拉取放大器列表
/upscaler R-ESRGAN 4x+      # 切换到指定放大器
```

从 SD WebUI API 实时获取可用放大器列表，或切换高分修复使用的放大器。仅在启用高分修复（`enable_hr=true`）时生效。

#### `/listmodules` - 查看可用附加模块

```
/listmodules
```

从 SD WebUI（SD-Forge）拉取可用的附加模块列表（VAE / Text Encoder），并标注当前已激活的模块。

#### `/addmodule <模块名>` - 激活附加模块

```
/addmodule vae-ft-mse-840000-ema-pruned.safetensors
/addmodule clip_l.safetensors
```

将指定模块加入当前会话的激活列表，后续所有绘图请求（`/draw` 命令和 Action）都会附带这些模块。重启后自动清空，若需默认启用请在配置文件中设置。

#### `/removemodule <模块名>` - 取消激活附加模块

```
/removemodule vae-ft-mse-840000-ema-pruned.safetensors
```

从当前会话的激活列表中移除指定模块。

#### `/clearmodules` - 清空所有激活的附加模块

```
/clearmodules
```

清空当前会话所有已激活的附加模块。

#### `/ch` - 撤回机器人消息

回复机器人发送的目标消息后使用 `/ch` 可撤回该消息；不回复时尝试撤回本会话最近发送的图片。撤回功能使用 NapCat HTTP API，相关地址和令牌在 `[recall]` 中配置。若无法从数据库确认目标消息的发送者或平台 ID，插件会拒绝撤回，避免误删其他消息。

通过本插件撤回图片成功后，对应历史消息会保留图片描述并标记为已撤回，同时保存撤回动作记录，让机器人在后续对话中了解图片状态。历史消息或动作记录需要处于 MaiBot 的上下文窗口内，已开始生成的回复不会自动刷新。通过其他客户端或管理员直接撤回的消息不在此功能范围内。

## ⚙️ 配置说明

### API 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api.base_url` | string | `http://localhost:7860` | Stable Diffusion WebUI API 地址 |

### 生成参数配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `generation.quality_prompt` | string | `masterpiece, best quality, highly detailed` | 默认质量提示词 |
| `generation.content_prompt` | string | `""` | 默认内容提示词 |
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
| `generation.hr_second_pass_steps` | int | `0` | 高分修复二次采样步数，0 表示与首次相同 |
| `generation.denoising_strength` | float | `0.7` | 去噪强度 |
| `generation.available_samplers` | list | `["Euler a", ...]` | 可用的采样器列表（API 不可用时的备用列表） |
| `generation.available_schedulers` | list | `["Automatic", ...]` | 可用的调度器列表（API 不可用时的备用列表） |
| `generation.available_upscalers` | list | `[]` | 可用放大器列表（API 不可用时的备用列表，留空则从 API 实时拉取） |
| `generation.default_additional_modules` | list | `[]` | 默认外挂附加模块列表（VAE / Text Encoder），填写模块的 model_name，留空则不启用 |

### 机器人配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `bot.appearance_description` | string | `a cute anime girl...` | 机器人外观描述（用于自画像） |

### 角色标签检索配置

`[tag_retrieval]` 控制角色 Tool 与规划前查询，`[character_query]` 单独控制 `/chartag` 命令。向量与重排接口默认使用 SiliconFlow；完整字段、首次索引行为和故障降级见 [角色标签智能检索指南](docs/TAG_RETRIEVAL_GUIDE.md)。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `tag_retrieval.enabled` | `true` | 启用角色标签 Tool 检索 |
| `tag_retrieval.prefetch_before_plan` | `true` | 绘图规划前识别角色并注入查询事实 |
| `tag_retrieval.api_key` | `""` | 留空时只使用本地 SQLite 查询 |
| `tag_retrieval.embedding_model` | `Qwen/Qwen3-Embedding-4B` | 角色及查询文本的向量模型 |
| `tag_retrieval.rerank_model` | `Qwen/Qwen3-Reranker-4B` | 候选重排模型 |
| `tag_retrieval.batch_size` | `32` | 首次构建索引的向量请求批次大小 |
| `tag_retrieval.candidate_count` | `30` | 向量召回候选数量，另合并名称匹配候选 |
| `tag_retrieval.timeout` | `60` | 单次检索接口请求超时秒数 |

### 画师风格配置

插件支持配置多个画师风格的 tag 组合，用户可以在对话中指定使用哪个风格。**注意：只有用户明确指定风格时才会使用这些 tag，未指定时不会添加任何风格标签。**

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `artist_styles.enabled` | bool | `false` | 是否启用画师风格功能 |
| `artist_styles.styles` | dict | 包含多个示例风格 | 画师风格标签配置（字典格式，键为中文风格名称，值为对应的英文 tag 串） |

#### ⚠️ 重要：修复自动生成的配置格式

自动生成的 `config.toml` 文件中，中文键名可能没有双引号，例如：

```toml
# ❌ 错误格式（自动生成的）
[artist_styles.styles]
画师bakup = "naga u, (tyakomes:0.95), henreader, baku-p"
画师柚子社团 = "Yuzusoft, Senren Banka"
```

**你需要手动修改为正确格式（给中文键名添加双引号）：**

```toml
# ✅ 正确格式（手动修改后）
[artist_styles.styles]
"画师bakup" = "naga u, (tyakomes:0.95), henreader, baku-p"
"画师柚子社团" = "Yuzusoft, Senren Banka"
```

#### 配置说明

**风格标签可以包含：**
1. **通用风格描述**: 如 `anime style, vibrant colors, cel shading`
2. **画师名称标签**: 如 `naga u, tyakomes, henreader, baku-p`
3. **带权重的画师标签**: 如 `(tyakomes:0.95), (naga u:1.2)` - 权重范围通常为 0.5-1.5，数值越大影响越强

**TOML 配置格式要求：**
- **中文键名必须用双引号包裹**，例如 `"动漫风格" = "..."`
- 如果键名是纯英文或数字，可以不加引号
- **自动生成的配置文件中中文键名可能缺少引号，需要手动添加**
- 初始配置文件中包含多个示例风格（画师bakup、画师柚子社团等），你可以参考它们添加更多风格
- 全部配置字段与默认值请参考 [config.py](config.py)

#### 默认包含的示例风格

自动生成的配置文件会包含以下示例风格（记得添加双引号）：

- `"画师bakup"` - naga u, (tyakomes:0.95), henreader, baku-p
- `"画师柚子社团"` - Yuzusoft, Senren Banka
- `"画师混合A"` - (naga u:1.1), (tyakomes:0.9), vibrant colors
- `"画师混合B"` - Yuzusoft, (henreader:0.95), detailed

#### 配置示例

```toml
[artist_styles]
enabled = true

[artist_styles.styles]
"画师bakup" = "naga u, (tyakomes:0.95), henreader, baku-p"
"画师柚子社团" = "Yuzusoft, Senren Banka"
"画师混合A" = "(naga u:1.1), (tyakomes:0.9), vibrant colors"
"画师混合B" = "Yuzusoft, (henreader:0.95), detailed"
"动漫" = "anime style, vibrant colors, cel shading, clean lines"
"写实" = "photorealistic, ultra detailed, 8k, professional photography"
"油画" = "oil painting, traditional art, brush strokes, canvas texture"
```

#### 使用方法

启用画师风格功能后，用户可以在对话中指定风格：

```
用户: 用画师bakup风格画一个女孩
机器人: [使用 "naga u, (tyakomes:0.95), henreader, baku-p" 标签生成图片]

用户: 用画师柚子社团风格画一个场景
机器人: [使用 "Yuzusoft, Senren Banka" 标签生成图片]

用户: 用动漫风格画一个猫耳娘
机器人: [使用 "动漫" 风格的 tag 生成图片]

用户: 画一个女孩（未指定风格）
机器人: [不使用任何风格标签，仅使用用户描述和质量提示词生成]
```

**重要：** 只有用户明确指定风格时才会使用对应的风格标签，如果用户没有指定风格，则不会添加任何风格相关的 tag。

#### 画师标签说明

**常见画师标签示例：**
- `naga u` - 知名插画师风格
- `tyakomes` - 特定画师风格
- `henreader` - 特定画师风格
- `baku-p` - 特定画师风格

**权重语法：**
- `(artist:1.0)` - 标准强度（默认）
- `(artist:0.8)` - 降低影响（80%）
- `(artist:1.2)` - 增强影响（120%）
- 可以组合多个画师：`(naga u:1.1), (tyakomes:0.95), henreader`

**提示：** 画师标签会直接影响生成图像的艺术风格，建议根据实际效果调整权重值。

### 消息撤回配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `recall.auto_recall_enabled` | bool | `false` | 是否在绘图后自动撤回图片 |
| `recall.auto_recall_delay` | int | `60` | 自动撤回延迟时间（秒） |
| `recall.group_mode` | string | `whitelist` | 群聊自动撤回模式：白名单群不撤回；黑名单仅名单内群撤回 |
| `recall.group_ids` | list | `[]` | 自动撤回群聊黑白名单，支持字符串或数字群号 |
| `recall.max_recall_time_limit` | int | `120` | 允许撤回的最大消息年龄（秒） |
| `recall.napcat_api_url` | string | `http://localhost:3000` | NapCat HTTP API 地址 |
| `recall.napcat_api_token` | string | `""` | NapCat HTTP API Token，可留空 |

白名单模式下，名单内群不会自动撤回；黑名单模式下，只有名单内群会自动撤回。私聊不受群名单影响。智能绘图 Action 和 `/draw` 命令的每张图片都会单独追踪，连续发送多张图片时分别撤回；无法唯一确认平台消息 ID 时会跳过自动撤回，不会改撤其他消息。

```toml
[recall]
auto_recall_enabled = true
auto_recall_delay = 60
group_mode = "whitelist"
group_ids = ["123456789"]
max_recall_time_limit = 120
napcat_api_url = "http://localhost:3000"
napcat_api_token = ""
```

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
- `style`: 画师风格名称（可选，当启用风格功能且用户指定风格时使用）
- `content_prompt`: 补充内容提示词（可选，英文）
- `width`: 图像宽度（可选）
- `height`: 图像高度（可选）
- `enable_hr`: 是否启用高分修复（可选）
- `hr_second_pass_steps`: 高分修复二次采样步数（可选）

### RecallAction

智能撤回动作，位于 `actions/recall_action.py`。用户明确要求撤回机器人消息时执行，优先撤回被回复的目标；未指定目标时尝试撤回本会话最近发送的机器人消息。

## 🔎 Tool 与事件处理器

`tools/character_tag_tool.py` 中的 `CharacterTagLookupTool` 提供 `character_tag_lookup`，接收角色名与可选作品名，最多返回三个候选的角色名、作品、`trigger` 和 `core_tags`。检索实现集中在 `retrieval/`，包括数据源适配、异步接口、向量索引与混合检索服务。

`events/character_tag_context.py` 中的 `CharacterTagContextHandler` 在绘图规划前调用角色 Tool，将结果保存为当前会话可见的事实上下文，供规划器组装 Action 提示词。需要在 MaiBot 本体启用 `[tool].enable_tool` 并配置支持工具调用的 `tool_use` 模型；插件通过 `plugin.py` 注册 Tool 与事件处理器。

## 💻 Command 组件说明

### DrawCommand

直接绘图命令，用户可以通过命令立即生成图片。

**命令格式**: `/draw <描述>`

### CharacterTagCommand

查询角色的绘图标签。按角色名（可选作品名）模糊匹配 `data/character_tags.db`，以合并转发消息返回缩略图、触发标签和核心标签。可通过 `[character_query]` 配置节开关或调整返回数量。

**命令格式**:
- `/chartag <角色名>` - 仅按角色名查询
- `/chartag <角色名>,<作品名>` - 按角色名和作品名查询（别名：`/查角色`、`/角色标签`）

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

查看或切换调度器，从 SD API 实时拉取列表（API 不可用时回退到配置文件列表）。

**命令格式**:
- `/scheduler` - 从 API 拉取调度器列表
- `/scheduler <调度器传参名>` - 切换到指定调度器

### SwitchUpscalerCommand

查看或切换高分修复放大器，从 SD API 实时拉取列表（API 不可用时回退到配置文件中的 `available_upscalers` 列表）。仅在启用高分修复时生效。

**命令格式**:
- `/upscaler` - 从 API 拉取放大器列表
- `/upscaler <放大器名>` - 切换到指定放大器

### ListModulesCommand

查看 SD WebUI（SD-Forge）可用的附加模块列表（VAE / Text Encoder）。需要 SD-Forge 支持 `/sdapi/v1/sd-modules` 端点。

**命令格式**: `/listmodules`

### AddModuleCommand

将指定附加模块加入当前会话的激活列表，后续绘图请求将通过 `forge_additional_modules` 字段附带这些模块。重启后自动清空。

**命令格式**: `/addmodule <模块名>`

### RemoveModuleCommand

从当前会话的激活列表中移除指定附加模块。

**命令格式**: `/removemodule <模块名>`

### ClearModulesCommand

清空当前会话所有已激活的附加模块。

**命令格式**: `/clearmodules`

### RecallCommand

通过 NapCat HTTP API 撤回被回复的机器人消息，未回复目标时尝试撤回本会话最近发送的图片。

**命令格式**: `/ch`

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

运行依赖包含 `aiohttp` 与 `numpy`（用于角色向量索引与余弦计算）。安装依赖和测试工具：

```powershell
python -m pip install aiohttp numpy pytest
python -m pytest tests -v
```

### 文件结构

```text
ai_drawing_plugin/
├── README.md                  # 安装、配置与使用入口
├── docs/                      # 项目说明文档
│   ├── CONFIG_FIX_GUIDE.md     # 配置文件修复指南
│   ├── NSFW_FILTER_GUIDE.md    # 图像审查指南
│   ├── reference/             # 本地第三方开发参考资料（Git 忽略）
│   ├── STRUCTURE.md           # 模块职责与扩展方式
│   └── TAG_RETRIEVAL_GUIDE.md  # 角色标签检索指南
├── plugin.py                  # 插件入口及全部组件注册
├── config.py                  # 配置字段、默认值与配置节描述
├── sd_client.py               # 异步 Stable Diffusion API 客户端
├── image_review.py            # 图像审查与名单判断
├── actions/                   # 智能绘图、智能撤回动作
├── commands/                  # 绘图、角色查询、模型与模块管理等命令
├── tools/                     # 角色标签查询 Tool
├── events/                    # 绘图规划前的角色事实注入
├── retrieval/                 # 数据源、向量接口、索引与混合检索
├── utils/                     # SQLite 查询、绘图队列、消息与撤回管理
├── tests/                     # 数据库、检索与 Tool 集成测试
├── _manifest.json             # 插件版本、组件声明等元数据
├── LICENSE                    # AGPL-3.0 许可证
├── data/                      # 本地角色库与向量缓存（Git 忽略）
└── thumbs/                    # 本地角色缩略图（可选，Git 忽略）
```

`data/`、`thumbs/` 和运行配置 `config.toml` 属于部署时准备或生成的本地资源。本地配置示例 `config_example.toml`、`config.toml.example` 也已被 Git 忽略，不随仓库分发。开发用第三方参考资料集中在 `docs/reference/`，不随插件发布。各源码文件的职责见 [项目结构说明](docs/STRUCTURE.md)。

### 开发与验证

新增 Action 或 Command 时在相应包中导出，再在 `plugin.py` 注册；新增 Tool 或事件处理器时同样在 `plugin.py` 注册组件信息，并同步维护 `_manifest.json` 的组件声明。优先修改模块化代码。

测试使用临时 SQLite 数据库、模拟检索接口与 MaiBot 接口替身，不依赖真实角色库和外部密钥。涉及真实绘图、工具调用上下文或消息发送的变更，还需在 MaiBot 中进行部署验证。

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
