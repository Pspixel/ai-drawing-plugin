# 🛡️ NSFW 内容过滤指南

## ⚠️ 重要说明

**负面提示词（Negative Prompt）无法 100% 阻止 NSFW 内容的生成。** 这是 Stable Diffusion 的固有限制，不是插件的问题。

---

## 🔍 为什么负面提示词不能完全阻止 NSFW？

### 1. **模型训练数据的影响**
- 如果使用的模型在 NSFW 数据上训练过，模型会有生成这类内容的倾向
- 某些动漫风格模型（如 Anything、NovelAI 系列）对 NSFW 内容更敏感
- 模型的"记忆"比负面提示词的影响更强

### 2. **提示词权重机制**
- 正面提示词的权重通常比负面提示词更强
- 如果正面提示词中包含某些敏感词汇（如 "sexy", "attractive", "revealing" 等），可能会触发 NSFW 内容
- 负面提示词只是"建议"，不是"强制"

### 3. **CFG Scale 的影响**
- `cfg_scale` 值过高（>12）会让模型过度遵循提示词，可能产生意外结果
- 值过低（<5）会让负面提示词失效

### 4. **采样器的差异**
- 不同采样器对负面提示词的响应程度不同
- 某些采样器（如 DDIM）对负面提示词的响应较弱

---

## ✅ 有效的解决方案

### 🥇 方案 1: 使用 SFW 模型（最有效）

**这是最根本、最有效的解决方法！**

#### 推荐的 SFW 模型：
- **Stable Diffusion 2.1** - 官方模型，默认过滤 NSFW
- **Realistic Vision V5.1 (SFW 版本)** - 写实风格，SFW 版本
- **DreamShaper (SFW 版本)** - 通用模型，有 SFW 版本
- **Pastel Mix (SFW 版本)** - 动漫风格，SFW 版本

#### 如何切换模型：
```bash
# 在聊天中使用命令列出 SD 中的所有可选模型
/switchmodel

# 切换到指定模型（支持模糊匹配）
/switchmodel model_name.safetensors

# 或在 Stable Diffusion WebUI 中手动切换
```

---

### 🥈 方案 2: 增强负面提示词权重

在负面提示词中使用权重语法：

```toml
# config.toml 中的配置
negative_prompt = "(nsfw:1.5), (nude:1.5), (explicit:1.5), (sexual:1.5), (porn:1.5), (hentai:1.5), lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"
```

#### 权重语法说明：
- `(word)` - 权重 1.1
- `((word))` - 权重 1.21
- `(word:1.5)` - 权重 1.5（推荐）
- `(word:2.0)` - 权重 2.0（最高）

---

### 🥉 方案 3: 调整生成参数

#### 1. 降低 CFG Scale
```toml
# 推荐值: 6.0-8.0
cfg_scale = 7.0
```

#### 2. 使用更保守的采样器
```toml
# 推荐采样器
sampler_name = "Euler a"  # 或 "DPM++ 2M Karras"
```

#### 3. 调整质量提示词
```toml
# 添加 SFW 相关的质量词
quality_prompt = "masterpiece, best quality, highly detailed, safe for work, appropriate, family friendly"
```

---

### 🛠️ 方案 4: 使用 Stable Diffusion WebUI 的安全功能

#### 1. 启用 Safety Checker（安全检查器）
在 Stable Diffusion WebUI 的设置中启用：
```
Settings -> User Interface -> Enable Safety Checker
```

#### 2. 使用 NSFW Filter 扩展
安装 WebUI 扩展：
- **sd-webui-nsfw-filter** - 自动检测和过滤 NSFW 图片
- **sd-webui-safety-checker** - 增强的安全检查

---

## 📋 完整的 NSFW 过滤配置示例

```toml
[generation]
# 质量提示词 - 添加 SFW 相关词汇
quality_prompt = "masterpiece, best quality, highly detailed, safe for work, appropriate, family friendly, wholesome"

# 内容提示词 - 避免使用敏感词汇
content_prompt = ""

# 负面提示词 - 使用高权重的 NSFW 过滤词
negative_prompt = "(nsfw:1.8), (nude:1.8), (explicit:1.8), (sexual:1.8), (porn:1.8), (hentai:1.8), (naked:1.5), (underwear:1.3), (revealing:1.3), lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"

# CFG Scale - 使用适中的值
cfg_scale = 7.0

# 采样器 - 使用保守的采样器
sampler_name = "Euler a"

# 采样步数 - 不要过高
steps = 20
```

---

## 🚨 用户输入的风险

即使配置了完善的 NSFW 过滤，**用户输入的提示词仍然可能触发 NSFW 内容**。

### 高风险词汇示例：
- 身体部位相关: "chest", "legs", "body"
- 服装相关: "bikini", "lingerie", "tight", "revealing"
- 姿势相关: "lying", "pose", "seductive"
- 描述词: "sexy", "hot", "attractive", "beautiful"

### 建议：
1. **在 Action 组件中添加提示词过滤**
2. **使用 LLM 重写用户提示词**，移除敏感词汇
3. **添加用户提示和警告**

---

## 🎯 最佳实践总结

### ✅ 推荐做法：
1. **使用 SFW 模型**（最重要！）
2. 在负面提示词中使用高权重的 NSFW 过滤词
3. 保持 `cfg_scale` 在 6.0-8.0 之间
4. 在质量提示词中添加 "safe for work", "appropriate" 等词
5. 启用 Stable Diffusion WebUI 的 Safety Checker

### ❌ 避免做法：
1. 不要使用专门的 NSFW 模型
2. 不要在提示词中使用敏感词汇
3. 不要将 `cfg_scale` 设置过高（>12）
4. 不要完全依赖负面提示词

---

## 📞 技术支持

如果仍然遇到 NSFW 内容问题：

1. **检查模型**: 确认使用的是 SFW 模型
2. **检查提示词**: 查看是否包含敏感词汇
3. **调整参数**: 降低 `cfg_scale`，调整采样器
4. **启用安全检查**: 在 WebUI 中启用 Safety Checker
5. **更换模型**: 尝试使用官方的 Stable Diffusion 2.1

---

## 🔗 相关资源

- [Stable Diffusion WebUI Wiki](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki)
- [Safe Models List](https://civitai.com/models?tag=sfw)
- [Negative Prompt Guide](https://stable-diffusion-art.com/negative-prompt/)

---

**最后提醒**: 负面提示词是辅助手段，**使用 SFW 模型才是根本解决方案**！
