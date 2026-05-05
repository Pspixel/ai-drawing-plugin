# 图像审查功能指南

本插件支持通过视觉模型对生成的图像进行内容审查，可配置黑白名单控制审查范围。

## 功能概述

- 使用视觉模型（如 LLaVA、GPT-4o 等）判断图像是否包含违规内容
- 支持私聊和群聊两套独立的黑白名单
- 违规图像会被拦截，不发送给用户
- 兼容 OpenAI 格式的多模态 API

## 配置说明

### 基础配置

```toml
[image_review]
# 是否启用图像审查功能
enabled = false
# 视觉模型 API 地址（OpenAI 兼容格式）
api_base_url = "http://127.0.0.1:11434/v1"
# API 密钥（可为空）
api_key = ""
# 视觉模型名称
model_name = "llava:13b"
# 审查提示词（要求模型返回 JSON 格式）
review_prompt = """请判断这张图片是否包含色情、暴力或违规内容。
请只返回一个 JSON 对象，格式如下：
{"safe": true/false, "reason": "违规原因（如果违规的话）"}
如果是正常图片，safe 为 true；如果包含违规内容，safe 为 false 并说明原因。"""
```

### 黑白名单配置

插件提供两套独立的黑白名单系统：群聊和私聊。

#### 群聊配置

```toml
# 群聊黑名单：名单中的群会被审查
[group_blacklist]
enabled = false
group_ids = []  # 群ID列表，例如 [123456789, 987654321]

# 群聊白名单：名单中的群会被审查
[group_whitelist]
enabled = false
group_ids = []  # 群ID列表
```

#### 私聊配置

```toml
# 私聊黑名单：名单中的用户会被审查
[private_blacklist]
enabled = false
user_ids = []  # 用户ID列表，例如 ["10001", "10002"]

# 私聊白名单：名单中的用户会被审查
[private_whitelist]
enabled = false
user_ids = []  # 用户ID列表
```

## 黑白名单逻辑

| 审查总开关 | 黑白名单状态 | 审查行为 |
|-----------|------------|---------|
| 关闭 | 任意 | 不审查任何图像，直接发送 |
| 开启 | 黑白名单都未启用 | 不审查任何图像 |
| 开启 | 只启用白名单 | 仅白名单中的用户/群审查 |
| 开启 | 只启用黑名单 | 仅黑名单中的用户/群审查 |
| 开启 | 黑白名单同时启用 | 命中任一名单都审查 |

## 使用示例

### 示例 1：审查所有群聊图像

```toml
[image_review]
enabled = true
api_base_url = "http://127.0.0.1:11434/v1"
model_name = "llava:13b"

# 不启用任何名单 = 审查总开关开启但不审查任何人
# 如需审查所有群，请将所有群ID加入白名单
[group_whitelist]
enabled = true
group_ids = [123, 456, 789]  # 填入所有需要审查的群ID
```

### 示例 2：只审查特定群

```toml
[image_review]
enabled = true

[group_blacklist]
enabled = true
group_ids = [123456789]  # 只有这个群会被审查
```

### 示例 3：只审查特定用户的私聊

```toml
[image_review]
enabled = true

[private_blacklist]
enabled = true
user_ids = ["10001", "10002"]  # 只有这些用户会被审查
```

## 视觉模型推荐

### 本地部署（推荐）

- **LLaVA**: 开源视觉语言模型，支持本地部署
  - Ollama: `ollama run llava:13b`
  - vLLM: 支持 OpenAI 兼容 API

- **Qwen-VL**: 阿里通义千问视觉模型
  - 支持 Ollama 部署

### 云端 API

- **GPT-4o**: OpenAI 多模态模型
- **Claude 3**: Anthropic 多模态模型
- **通义千问 VL**: 阿里云 API

## 审查提示词优化

默认的审查提示词已能满足大部分需求，但你也可以根据场景自定义：

```toml
review_prompt = """请判断这张图片是否包含以下违规内容：
1. 色情或裸露
2. 暴力或血腥
3. 政治敏感
4. 其他违规内容

请只返回 JSON：{"safe": true/false, "reason": "原因"}"""
```

## 常见问题

### Q: 审查速度慢怎么办？

**A**: 可以尝试：
1. 使用更轻量的视觉模型（如 llava:7b）
2. 优化审查提示词，减少输出长度
3. 考虑使用云端 API

### Q: 审查结果不准确怎么办？

**A**: 可以：
1. 调整审查提示词，明确违规标准
2. 尝试更强的视觉模型
3. 在提示词中提供具体的判断标准

### Q: 如何跳过某些群的审查？

**A**: 不将该群的 ID 加入任何名单即可。黑白名单是"审查名单"，不在名单中就不会被审查。

## 技术实现

审查流程：
1. 图像生成完成后，获取 base64 编码
2. 调用视觉模型 API，发送图像和审查提示词
3. 解析模型返回的 JSON 结果
4. 如果 `safe: false`，拦截图像并向用户发送违规提示
5. 如果 `safe: true`，正常发送图像

API 请求格式（OpenAI 兼容）：
```json
{
  "model": "llava:13b",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "审查提示词"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
      ]
    }
  ],
  "max_tokens": 200,
  "temperature": 0.1
}
```

返回格式：
```json
{
  "safe": false,
  "reason": "图片包含裸露内容"
}
```
