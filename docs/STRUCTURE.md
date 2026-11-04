# AI 绘图插件代码结构

插件入口为根目录的 [plugin.py](../plugin.py)，负责注册 Action、Command、Tool 和事件处理器。配置字段集中在 [config.py](../config.py)，插件元数据与组件声明位于 [_manifest.json](../_manifest.json)。安装与使用方法见 [README](../README.md)。

本文所有源码路径均相对于插件根目录。

## 目录结构

```text
ai_drawing_plugin/
├── README.md
├── docs/                         # 项目说明与开发参考资料
│   ├── CONFIG_FIX_GUIDE.md
│   ├── NSFW_FILTER_GUIDE.md
│   ├── STRUCTURE.md
│   ├── TAG_RETRIEVAL_GUIDE.md
│   └── reference/                # 本地第三方资料，Git 忽略
├── plugin.py                     # 插件入口与组件注册
├── config.py                     # 配置 Schema、默认值与配置节描述
├── sd_client.py                  # 异步 Stable Diffusion API 客户端
├── image_review.py               # 图像审查
├── actions/
│   ├── __init__.py
│   ├── drawing_action.py         # 智能绘图
│   └── recall_action.py          # 智能撤回
├── commands/
│   ├── __init__.py
│   ├── draw_command.py           # /draw
│   ├── character_tag_command.py  # /chartag
│   ├── help_command.py           # /drawhelp
│   ├── model_commands.py         # /drawmodel、/switchmodel
│   ├── sampler_commands.py       # /sampler、/scheduler、/upscaler
│   ├── module_commands.py        # 附加模块管理
│   └── recall_command.py         # /ch
├── tools/
│   ├── __init__.py
│   └── character_tag_tool.py     # character_tag_lookup
├── events/
│   ├── __init__.py
│   └── character_tag_context.py  # 绘图规划前的角色标签事实注入
├── retrieval/
│   ├── __init__.py
│   ├── source.py                 # 通用记录、角色语料与名称匹配
│   ├── client.py                 # 异步 Embedding / Rerank 请求
│   ├── index.py                  # 余弦计算与本地向量缓存
│   ├── service.py                # 索引任务、混合检索与降级
│   └── rules.py                  # Action 共用角色事实规则
├── utils/
│   ├── __init__.py
│   ├── character_tag_db.py       # /chartag 使用的只读 SQLite 查询
│   ├── drawing_queue.py          # 绘图任务队列
│   ├── message_generator.py      # LLM 风格化回复与文本清理
│   └── recall_manager.py         # 发送记录追踪与 NapCat 撤回
├── tests/
│   ├── test_character_tag_db.py
│   ├── test_tag_retrieval.py
│   └── test_character_tag_tool.py
├── _manifest.json
├── LICENSE
├── data/                         # 本地角色数据库与向量缓存，Git 忽略
└── thumbs/                       # 本地缩略图，Git 忽略
```

`AGENTS.md` 是根目录的开发指令入口。运行配置 `config.toml` 由 MaiBot 自动生成。全部配置字段与默认值以 `config.py` 为准；本地配置示例 `config_example.toml` 和 `config.toml.example` 已被 Git 忽略。目录树省略了 Git、编辑器配置和 Python 缓存文件。

## 模块职责与调用流程

### 绘图

`actions/drawing_action.py` 与 `commands/draw_command.py` 分别处理模型规划的绘图动作和用户的 `/draw` 命令，负责组合提示词、读取参数并将任务交给 `utils/drawing_queue.py`。队列通过 `sd_client.py` 调用 Stable Diffusion WebUI API，生成结果按配置交给 `image_review.py` 审查，再发送图片并记录撤回信息。

`commands/model_commands.py`、`commands/sampler_commands.py` 与 `commands/module_commands.py` 管理模型、采样器、调度器、放大器及 SD-Forge 附加模块。`utils/message_generator.py` 使用 MaiBot 模型生成开始、成功、失败和错误回复，异常时提供默认文本。

### 角色标签检索

`events/character_tag_context.py` 在 `ON_PLAN` 阶段识别绘图请求中的明确角色，并调用 `tools/character_tag_tool.py` 提供的 `character_tag_lookup`。结果通过 MaiBot 动作记录 API 写入当前会话上下文，让规划器在生成绘图 Action 参数时读取角色事实。

Tool 使用 `retrieval/service.py` 检索。`retrieval/source.py` 将角色数据库记录转换为通用语料；`retrieval/client.py` 请求向量和重排服务；`retrieval/index.py` 在本地缓存向量并计算相似度。服务合并名称匹配和向量候选后重排，最多返回三个结果，并在服务不可用时降级。

`utils/character_tag_db.py` 单独服务于 `/chartag` 的中文名称查询及缩略图读取。修改 Tool 语义检索时应保持该命令的原有查询行为。索引构建、缓存路径和接口配置见 [角色标签智能检索指南](TAG_RETRIEVAL_GUIDE.md)。

### 撤回与审查

`actions/recall_action.py` 与 `commands/recall_command.py` 共用 `utils/recall_manager.py`，通过 NapCat HTTP API 撤回机器人消息。智能绘图和 `/draw` 按 `[recall]` 配置为每张图片建立独立的自动撤回任务，并可通过群聊黑白名单控制自动撤回范围。

`image_review.py` 封装视觉模型审查，并依据 `[image_review]` 中的群聊和私聊名单决定是否审查。配置入口见 [README 的图像审查说明](../README.md#图像审查配置)。

## 扩展与验证

新增 Action 或 Command 时，在对应目录创建模块、继承 MaiBot 基类并从包中导出，然后在 `plugin.py` 注册组件。新增 Tool 时继承 `BaseTool`，按当前 MaiBot 接口定义参数，并通过 `get_tool_info()` 注册；新增事件处理器时继承 `BaseEventHandler` 并通过 `get_handler_info()` 注册。组件声明同步更新 `_manifest.json`。

新增数据源可复用 `retrieval/source.py` 中的 `TagRecord` 与现有向量、重排、索引组件。纯检索逻辑应保持不依赖 MaiBot，便于单独测试。`utils/__init__.py` 会导入依赖宿主的模块，独立查询模块可按现有测试采用文件路径加载方式。

在插件根目录执行：

```powershell
python -m pip install aiohttp numpy pytest
python -m pytest tests -v
```

测试使用临时数据库、模拟接口与 MaiBot 接口替身。涉及真实绘图、消息发送和工具上下文的变更，还需将完整插件放入 MaiBot 的 `plugins/` 目录并在部署环境验证。新增功能应在对应模块中实现，并由 `plugin.py` 统一注册。
