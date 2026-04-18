# AI 绘图插件代码结构

本插件采用模块化设计，代码结构清晰，便于维护和扩展。

## 📁 目录结构

```
ai_drawing_plugin/
├── __init__.py                 # 插件包初始化
├── plugin.py                   # 插件主文件（入口）
├── config.py                   # 配置定义模块
├── sd_client.py               # Stable Diffusion API 客户端
├── actions/                   # Action 组件目录
│   ├── __init__.py
│   └── drawing_action.py      # AI 绘图 Action
├── commands/                  # Command 组件目录
│   ├── __init__.py
│   ├── draw_command.py        # 绘图命令
│   ├── help_command.py        # 帮助命令
│   ├── model_commands.py      # 模型管理命令
│   └── sampler_commands.py    # 采样器/调度器命令
├── utils/                     # 工具模块目录
│   ├── __init__.py
│   └── message_generator.py  # LLM 风格化消息生成器
├── _manifest.json             # 插件清单
├── config.toml.example        # 配置文件示例
└── README.md                  # 插件文档
```

## 📦 模块说明

### 核心模块

#### `plugin.py` - 插件主文件
- 插件注册和初始化
- 组件注册
- 配置加载

#### `config.py` - 配置定义
- 配置 Schema 定义
- 配置节描述
- 默认值设置

#### `sd_client.py` - API 客户端
- Stable Diffusion WebUI API 封装
- 图像生成接口
- 模型管理接口

### Action 组件

#### `actions/drawing_action.py`
- **AIDrawingAction**: 智能绘图动作
- 根据对话上下文自动触发
- 支持自画像功能
- 集成 LLM 风格化回复

### Command 组件

#### `commands/draw_command.py`
- **DrawCommand**: `/draw` 命令
- 直接生成图片
- 支持自定义参数

#### `commands/help_command.py`
- **DrawHelpCommand**: `/drawhelp` 命令
- 显示帮助信息

#### `commands/model_commands.py`
- **CurrentModelCommand**: `/drawmodel` 命令
- **SwitchModelCommand**: `/switchmodel` 命令
- 模型查看和切换功能

#### `commands/sampler_commands.py`
- **SwitchSamplerCommand**: `/sampler` 命令
- **SwitchSchedulerCommand**: `/scheduler` 命令
- 采样器和调度器管理

### 工具模块

#### `utils/message_generator.py`
- **MessageGenerator**: 消息生成器类
- 使用 LLM 生成风格化回复
- 支持多种消息类型（开始/成功/失败/错误）
- 自动降级到默认消息

## 🔧 模块化优势

1. **职责分离**: 每个模块负责特定功能，代码清晰
2. **易于维护**: 修改某个功能只需编辑对应模块
3. **便于扩展**: 添加新命令只需创建新文件
4. **代码复用**: 公共功能（如消息生成）可被多个组件使用
5. **测试友好**: 每个模块可独立测试

## 🚀 添加新功能

### 添加新的 Command

1. 在 `commands/` 目录创建新文件
2. 继承 `BaseCommand` 类
3. 在 `commands/__init__.py` 中导出
4. 在 `plugin.py` 中注册

### 添加新的 Action

1. 在 `actions/` 目录创建新文件
2. 继承 `BaseAction` 类
3. 在 `actions/__init__.py` 中导出
4. 在 `plugin.py` 中注册

### 添加新的工具类

1. 在 `utils/` 目录创建新文件
2. 在 `utils/__init__.py` 中导出
3. 在需要的地方导入使用
