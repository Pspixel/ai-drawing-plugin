# 角色标签智能检索

插件版本 `1.3.0`，配置版本 `2.3.0`。`character_tag_lookup` Tool 接收必填的 `character_name` 和可选的 `copyright_name`，最多返回三个候选的角色名、作品、原始 `trigger` 和 `core_tags`。

## 安装与配置

安装插件运行依赖：

```powershell
python -m pip install aiohttp numpy
```

角色库位于插件的 `data/character_tags.db`。它需要包含现有的 `characters` 表及 `character`、`name_cn`、`copyright_cn`、`trigger`、`core_tags`、`count` 字段。数据库与可选索引不随 Git 提交；本插件不分发缩略图，需要时请根据 [AnimaDex](https://github.com/zetaneko/AnimaDex) 的说明自行获取。资源发布状态、下载校验和目录放置方式见 [README 的快速开始](../README.md#3-准备角色查询资源可选)。

首次启动后在 MaiBot 自动生成的插件 `config.toml` 中配置：

```toml
[tag_retrieval]
enabled = true
prefetch_before_plan = true
api_key = ""
embedding_url = "https://api.siliconflow.cn/v1/embeddings"
embedding_model = "Qwen/Qwen3-Embedding-4B"
rerank_url = "https://api.siliconflow.cn/v1/rerank"
rerank_model = "Qwen/Qwen3-Reranker-4B"
timeout = 60
batch_size = 32
candidate_count = 30
min_similarity = 0.45
min_rerank_score = 0.3
rerank_enabled = true
```

仅在本地运行配置填写 SiliconFlow 密钥。密钥字段在配置界面按密码显示；留空时只执行本地 SQLite 名称查询，不请求 Embedding 或 Rerank。配置有效密钥后，会把角色名称、作品、触发词和核心标签发送到配置的向量服务，把查询和候选语料发送到重排服务。

MaiBot 本体 `config/bot_config.toml` 的工具开关必须启用：

```toml
[tool]
enable_tool = true
```

同时在 MaiBot 的模型配置中启用可执行函数调用的 `tool_use` 任务模型。插件不修改这些本体配置。

## 绘图前如何获取标签

1. 启用检索并配置密钥后，插件注册时异步校验索引；索引尚未就绪时，工具查询会等待同一个索引任务完成。密钥留空时只查询 SQLite。
2. 规划前事件处理器识别包含绘图意图的用户消息，由 MaiBot 的 `tool_use` 模型判断是否有命名角色并构造 Tool 参数，单个请求最多查询三个角色。
3. 通过 MaiBot 工具 API 获取并执行 `character_tag_lookup`，将结果保存为当前会话可见的动作记录，再继续规划。
4. 绘图 Action 的提示规则要求从这些事实中选择角色，保留原始触发词并使用核心外观标签，结合用户的服装、动作、构图要求组装提示词。未命中、歧义未消除或服务不可用时不得编造角色触发标签。

这个事件桥接是必要的：所检查的 MaiBot 版本原生工具结果只进入回复生成器，而 Action 参数由独立规划器提前生成；该规划器还会在 `ON_PLAN` 后重建提示词，所以插件通过官方动作记录 API 传递事实。结果按会话保存，包含对应用户请求，避免不同会话或角色之间混用。

`prefetch_before_plan = true` 会为包含绘图意图的请求增加一次 MaiBot 工具模型调用。设为 `false` 可关闭规划前桥接，Tool 仍可供原生回复工具处理器调用，但此时不能保证 Action 规划前读到标签。桥接尊重本体工具开关及会话内禁用工具的设置。最近五分钟内，相同会话、发送者和消息原文只预查一次；查询异常时继续原有绘图流程。

Action 规则通过提示引导模型使用事实；最终提示词是否完全遵守规则仍取决于规划模型，需要在真实对话中验收。`/draw` 与 `/chartag` 保留原有逻辑，`character_query` 配置只控制 `/chartag`。

## 索引、检索与降级

语料包含中文名称、英文标识、作品、触发词和核心标签。索引保存在 `data/character_vectors.npz`，使用 NumPy 浮点向量与 JSON 元数据，不加载 pickle。启动时按数据库内容指纹、接口地址和 Embedding 模型 ID 判断缓存是否可复用，变化后完整重建；写入临时文件后原子替换。数据库读取、指纹计算、缓存读写和向量计算均在线程中执行，接口请求采用异步 HTTP。

配套预构建索引使用 `Qwen/Qwen3-Embedding-4B` 和默认的 SiliconFlow Embedding 接口地址；与数据库一起放置后，配置有效密钥即可按默认配置复用。查询时仍需请求 Embedding API，重排启用时还会请求 Rerank API，因此仍可能产生接口费用。密钥留空时不会加载或创建向量索引，只执行 SQLite 名称查询。

配置密钥后，如果索引缺失、损坏，或数据库内容、模型 ID、接口地址与索引不匹配，插件会为完整角色库重新构建索引，可能需要较长时间并产生接口费用。约 36,495 条记录、每批 32 条时，需要约 1,141 个向量请求；索引维度读取自接口响应。构建失败后当前查询降级为 SQLite，后续查询可在 60 秒冷却后重试。

查询合并默认的向量 Top 30 与最多 30 条 SQLite 名称候选，按记录标识去重，再重排并最多返回三条。重排失败则按余弦分数排序；查询向量请求失败或索引不可用则使用 SQLite。作品名对两类召回都执行包含过滤；不确定作品名时应省略该参数。名称查询同时覆盖中文名、英文标识和触发词，原有 `/chartag` 仍按中文名称查询。

`min_similarity` 过滤较弱语义候选，`min_rerank_score` 过滤低相关度重排结果。两者为可调启发式阈值，未经过当前模型与完整角色库的真实标定；向量检索不能保证识别所有别名和错字，也可能返回相似但无关的候选。应结合角色与作品确认身份，必要时请求用户消歧。

后续数据源可复用 `TagRecord`、`SiliconFlowClient` 和 `VectorIndex`，添加新的数据源适配器及独立 Tool。本版本不接入 Danbooru 标签数据源。

## 验证与部署验收

```powershell
python -m pip install pytest
python -m pytest tests -v
```

测试使用临时数据库、模拟接口、本地 HTTP 服务及严格的 MaiBot 接口替身，覆盖索引缓存、请求校验、混合候选、降级、Tool 注册、规划前事实保存与原有 Action 执行路径。

部署后检查组件列表中存在 `character_tag_lookup` 和 `character_tag_context`，并逐项验证：

| 场景 | 示例 | 检查项 |
| --- | --- | --- |
| 精确名称 | 画原神的甘雨在雪地里 | 查询返回库中原始触发词，规划提示词能看到角色事实 |
| 别名或错字 | 画赶雨 | 向量候选与作品是否正确；不能用模拟测试代替模型效果验证 |
| 作品消歧 | 查询甘雨，作品原神 | 候选仅来自匹配作品 |
| 无匹配 | 查询一个库中不存在的角色 | 不编造触发词，提示补充信息或使用明确外观描述 |
| 服务故障 | 模拟向量或重排不可用 | 相应降级生效，原绘图流程继续 |

当前开发环境的 81 项测试全部通过；另已对本地 36,495 条记录的真实角色库执行只读加载、精确名、英文标识、作品名过滤与无匹配查询。隔离外部初始化依赖后，使用同级 MaiBot 源码中的实际 `BaseTool`、`ToolInfo`、`ComponentRegistry` 和参数构建器验证了 Tool 注册、模型可见性、五元组参数及真实数据库调用。

同级 MaiBot 的 `[tool].enable_tool = true`，且已配置 `tool_use` 模型任务。当前插件无本地 `config.toml` 和检索 API 密钥，真实 SiliconFlow 协议与检索效果尚未验收；当前 Python 环境缺少宿主依赖 `toml`，完整 MaiBot 运行与真实对话验收也尚未执行。
