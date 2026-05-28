# 配置文件修复指南

## 问题说明

自动生成的 `config.toml` 文件中，中文键名可能没有双引号，这会导致 TOML 解析错误。

## 错误示例

```toml
# ❌ 错误格式（自动生成的）
[artist_styles.styles]
画师bakup = "naga u, (tyakomes:0.95), henreader, baku-p"
画师柚子社团 = "Yuzusoft, Senren Banka"
画师混合A = "(naga u:1.1), (tyakomes:0.9), vibrant colors"
画师混合B = "Yuzusoft, (henreader:0.95), detailed"
```

## 修复方法

**给所有中文键名添加双引号：**

```toml
# ✅ 正确格式（手动修改后）
[artist_styles.styles]
"画师bakup" = "naga u, (tyakomes:0.95), henreader, baku-p"
"画师柚子社团" = "Yuzusoft, Senren Banka"
"画师混合A" = "(naga u:1.1), (tyakomes:0.9), vibrant colors"
"画师混合B" = "Yuzusoft, (henreader:0.95), detailed"
```

## 快速修复步骤

1. 打开 `config.toml` 文件
2. 找到 `[artist_styles.styles]` 部分
3. 在每个中文键名前后添加双引号 `"`
4. 保存文件
5. 重启 MaiBot

## 规则说明

- **中文键名**：必须用双引号包裹，例如 `"画师bakup"`
- **英文键名**：可以不加引号，例如 `anime_style`（但加引号也可以）
- **值（tag 串）**：始终用双引号包裹

## 完整配置示例

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

# 英文键名可以不加引号（但加了也没问题）
anime_style = "anime, colorful"
"realistic_style" = "realistic, detailed"
```

## 使用方法

修复配置后，启用画师风格功能：

```toml
[artist_styles]
enabled = true  # 改为 true 启用功能
```

然后用户就可以在对话中指定风格：

```
用户: 用画师bakup风格画一个女孩
用户: 用画师柚子社团风格画一个场景
用户: 用动漫风格画一个猫耳娘
```

## 常见问题

**Q: 为什么自动生成的配置没有引号？**

A: 这是 Python TOML 生成器的限制，它不会自动给中文键名添加引号。需要手动修复。

**Q: 我可以用英文键名吗？**

A: 可以！如果使用英文键名（如 `artist_bakup`），就不需要加引号。但用户在对话中需要说英文风格名。

**Q: 修复后还是报错怎么办？**

A: 检查以下几点：
1. 确保每个中文键名都有双引号
2. 确保引号是英文双引号 `"` 而不是中文引号 `""`
3. 确保等号两边有空格
4. 参考 `config_example.toml` 文件的格式
