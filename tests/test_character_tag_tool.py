"""以严格的 MaiBot 接口替身验证组件注册、工具结果和规划时序。"""
import asyncio
import importlib
import json
import logging
import sqlite3
import sys
import tomllib
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parent.parent
PREFIX = "drawing_plugin_contract"


@pytest.fixture
def framework(monkeypatch, tmp_path):
    def module(name, **attributes):
        result = ModuleType(name)
        result.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    class ToolParamType(Enum):
        STRING = "string"

    class BaseTool:
        @classmethod
        def get_tool_info(cls):
            # 按本地 MaiBot 源码要求，参数必须是枚举类型的五元组。
            assert all(len(param) == 5 and isinstance(param[1], ToolParamType) for param in cls.parameters)
            return SimpleNamespace(name=cls.name, enabled=cls.available_for_llm, tool_parameters=cls.parameters)

        @classmethod
        def get_tool_definition(cls):
            cls.get_tool_info()
            return {"name": cls.name, "description": cls.description, "parameters": cls.parameters}

    class BasePlugin:
        def get_config(self, key, default=None):
            return self.values.get(key, default)

    class BaseAction:
        @classmethod
        def get_action_info(cls):
            return SimpleNamespace(name=cls.action_name, action_require=list(cls.action_require))

    class BaseEventHandler:
        def get_config(self, key, default=None):
            return getattr(self, "values", {}).get(key, default)

        @classmethod
        def get_handler_info(cls):
            return SimpleNamespace(name=cls.handler_name, event_type=cls.event_type)

    class ConfigField:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    module("src", __path__=[])
    system = module(
        "src.plugin_system", __path__=[], BaseTool=BaseTool, BasePlugin=BasePlugin,
        BaseAction=BaseAction, BaseEventHandler=BaseEventHandler, ConfigField=ConfigField,
        ActionActivationType=SimpleNamespace(ALWAYS="always"), ComponentInfo=object,
        EventType=SimpleNamespace(ON_PLAN="on_plan"), ToolParamType=ToolParamType,
        register_plugin=lambda cls: cls,
    )
    module("src.config", __path__=[])
    config = SimpleNamespace(tool=SimpleNamespace(enable_tool=True))
    module("src.config.config", global_config=config)
    calls, saved, sent, generated = [], [], [], []
    stream = SimpleNamespace(stream_id="会话甲", platform="测试")

    async def llm(**kwargs):
        calls.append(kwargs)
        return True, "", "", "测试模型", [SimpleNamespace(
            func_name="character_tag_lookup", args={"character_name": "甘雨", "copyright_name": "原神"},
        )]

    async def save(**kwargs):
        saved.append(kwargs)
        return kwargs

    tool_api = SimpleNamespace(get_tool_instance=lambda name, stream: tool_class())
    llm_api = SimpleNamespace(
        get_available_models=lambda: {"tool_use": object()}, generate_with_model_with_tools=llm,
    )
    module("src.plugin_system.apis", database_api=SimpleNamespace(store_action_info=save),
           llm_api=llm_api, tool_api=tool_api)
    module("src.plugin_system.core", __path__=[])
    announcements = SimpleNamespace(get_disabled_chat_tools=lambda chat: [])
    module("src.plugin_system.core.global_announcement_manager", global_announcement_manager=announcements)
    module("src.chat", __path__=[])
    module("src.chat.message_receive", __path__=[])
    module("src.chat.message_receive.chat_stream", get_chat_manager=lambda: SimpleNamespace(get_stream=lambda key: stream))

    module(PREFIX, __path__=[str(ROOT)])

    async def message(*args, **kwargs):
        return "测试绘图消息"

    module(f"{PREFIX}.utils", __path__=[], MessageGenerator=SimpleNamespace(generate_stylized_message=message),
           RecallManager=SimpleNamespace())

    class Queue:
        @staticmethod
        def queue_size():
            return 0

        @staticmethod
        async def enqueue(**kwargs):
            generated.append(kwargs)
            return False, None, "模拟绘图失败"

    module(f"{PREFIX}.utils.drawing_queue", DrawingQueue=Queue, QUEUE_MAX_SIZE=10)
    module(f"{PREFIX}.image_review", ImageReviewer=SimpleNamespace())
    commands = module(f"{PREFIX}.commands", __path__=[])
    for name in [
        "DrawCommand", "CharacterTagCommand", "DrawHelpCommand", "CurrentModelCommand", "SwitchModelCommand",
        "SwitchSamplerCommand", "SwitchSchedulerCommand", "SwitchUpscalerCommand", "ListModulesCommand",
        "AddModuleCommand", "RemoveModuleCommand", "ClearModulesCommand",
    ]:
        setattr(commands, name, type(name, (), {
            "get_command_info": classmethod(lambda cls: SimpleNamespace(name=cls.__name__)),
        }))
    module(f"{PREFIX}.commands.recall_command", RecallCommand=commands.DrawCommand)
    module(f"{PREFIX}.commands.module_commands", get_active_modules=lambda: [])
    module(f"{PREFIX}.commands.sampler_commands", get_active_sampler=lambda: None,
           get_active_scheduler=lambda: None, get_active_upscaler=lambda: None)
    module(f"{PREFIX}.actions.recall_action", RecallAction=type("RecallAction", (), {
        "get_action_info": classmethod(lambda cls: SimpleNamespace(name="recall")),
    }))

    path = tmp_path / "characters.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE characters (character TEXT, name_cn TEXT, copyright_cn TEXT, "
                           "trigger TEXT, core_tags TEXT, count INTEGER)")
        connection.executemany("INSERT INTO characters VALUES (?, ?, ?, ?, ?, ?)", [
            ("ganyu", "甘雨", "原神", "ganyu_(genshin_impact)", "blue hair, horns", 100),
            ("fan", "甘雨", "同人", "ganyu_fan", "black hair", 1),
        ])
    try:
        service_module = importlib.import_module(f"{PREFIX}.retrieval.service")
        client_class = importlib.import_module(f"{PREFIX}.retrieval.client").SiliconFlowClient
        service = service_module.CharacterRetrievalService(client_class(""), path, tmp_path / "index.npz")
        service_module.configure_service(service)
        tool_class = importlib.import_module(f"{PREFIX}.tools.character_tag_tool").CharacterTagLookupTool
        event_module = importlib.import_module(f"{PREFIX}.events.character_tag_context")
        plugin = importlib.import_module(f"{PREFIX}.plugin")
        yield SimpleNamespace(
            service=service, service_module=service_module, tool_class=tool_class,
            handler=event_module.CharacterTagContextHandler(), event_module=event_module,
            llm_api=llm_api, calls=calls, saved=saved, config=config, sent=sent, generated=generated,
            plugin=plugin, system=system, announcements=announcements,
        )
    finally:
        for name in list(sys.modules):
            if name == PREFIX or name.startswith(PREFIX + "."):
                sys.modules.pop(name, None)


def request_message(text="帮我画原神的甘雨", stream="会话甲"):
    return SimpleNamespace(plain_text=text, stream_id=stream, raw_message=text,
                           message_base_info={"user_id": "用户甲"}, llm_prompt="可用动作：ai_drawing")


def test_tool_fields_disambiguation_and_no_match(framework):
    async def run():
        tool = framework.tool_class()
        result = await tool.execute({"character_name": "甘雨", "copyright_name": "原神"})
        assert result["name"] == "character_tag_lookup"
        assert "ganyu_(genshin_impact)" in result["content"]
        assert "blue hair, horns" in result["content"]
        assert "同人" not in result["content"]
        result = await tool.execute({"character_name": "不存在"})
        assert "未找到" in result["content"] and "勿伪造" in result["content"]
        assert "不能为空" in (await tool.execute({}))["content"]

    asyncio.run(run())


def test_tool_unavailable_never_exposes_errors(framework, monkeypatch, caplog):
    async def failed(*args):
        raise RuntimeError("敏感响应内容")

    async def run():
        monkeypatch.setattr(framework.service, "search", failed)
        with caplog.at_level(logging.WARNING):
            result = await framework.tool_class().execute({"character_name": "甘雨"})
        assert "不可用" in result["content"] and "编造" in result["content"]
        assert "敏感响应内容" not in caplog.text + result["content"]
        framework.service.enabled = False
        assert "不可用" in (await framework.tool_class().execute({"character_name": "甘雨"}))["content"]

    asyncio.run(run())


def test_plugin_registers_tool_handler_and_action_rules(framework):
    plugin = framework.plugin.AIDrawingPlugin()
    plugin.values = {}
    components = plugin.get_plugin_components()
    names = [info.name for info, _ in components]
    assert "character_tag_lookup" in names
    assert "character_tag_context" in names
    action = next(info for info, _ in components if info.name == "ai_drawing")
    assert any("character_tag_lookup" in rule for rule in action.action_require)
    assert any("原样保留" in rule for rule in action.action_require)
    assert any("Tool 不计为绘图调用" in rule for rule in action.action_require)
    assert "numpy" in plugin.python_dependencies
    assert framework.tool_class.get_tool_info().enabled


def test_before_plan_stores_facts_and_deduplicates(framework):
    async def run():
        message = request_message()
        results = await asyncio.gather(framework.handler.execute(message), framework.handler.execute(message))
        assert all(result[:2] == (True, True) for result in results)
        assert len(framework.calls) == len(framework.saved) == 1
        saved = framework.saved[0]
        assert saved["action_name"] == "character_tag_lookup"
        assert saved["action_build_into_prompt"] is True
        assert saved["chat_stream"].stream_id == "会话甲"
        assert "ganyu_(genshin_impact)" in saved["action_prompt_display"]
        assert message.plain_text in saved["action_prompt_display"]
        assert framework.calls[0]["tool_options"][0]["name"] == "character_tag_lookup"
        await framework.handler.execute(message)
        assert len(framework.calls) == 1

    asyncio.run(run())


def test_bridge_skips_disabled_tools_and_non_drawing(framework, monkeypatch):
    async def run():
        await framework.handler.execute(request_message("天气怎么样"))
        assert not framework.calls
        framework.config.tool.enable_tool = False
        await framework.handler.execute(request_message())
        framework.config.tool.enable_tool = True
        framework.service.prefetch_before_plan = False
        await framework.handler.execute(request_message())
        framework.service.prefetch_before_plan = True
        monkeypatch.setattr(framework.announcements, "get_disabled_chat_tools", lambda key: ["character_tag_lookup"])
        await framework.handler.execute(request_message())
        assert not framework.calls

    asyncio.run(run())


def test_bridge_fails_open_and_does_not_cache_failure(framework, monkeypatch):
    async def failed(**kwargs):
        raise TimeoutError("模拟工具模型超时")

    async def run():
        monkeypatch.setattr(framework.llm_api, "generate_with_model_with_tools", failed)
        assert (await framework.handler.execute(request_message()))[:2] == (True, True)
        assert not framework.handler._processed
        assert not framework.saved

    asyncio.run(run())


def test_bridge_with_no_named_character_does_not_store_facts(framework, monkeypatch):
    async def no_tools(**kwargs):
        return True, "", "", "模型", None

    monkeypatch.setattr(framework.llm_api, "generate_with_model_with_tools", no_tools)
    asyncio.run(framework.handler.execute(request_message("画一张风景")))
    assert not framework.saved


def test_drawing_action_keeps_original_execution_and_trigger(framework):
    action_class = framework.plugin.AIDrawingAction

    async def send(text):
        framework.sent.append(text)

    action = action_class()
    action.get_config = lambda key, default=None: default
    action.action_data = {"prompt": "1girl, ganyu_(genshin_impact), blue hair, horns"}
    action.action_message = {"processed_plain_text": "画甘雨"}
    action.chat_stream = SimpleNamespace(stream_id="会话甲")
    action.send_text = send
    success, result = asyncio.run(action.execute())
    assert success is False and "模拟绘图失败" in result
    assert framework.generated[0]["txt2img_kwargs"]["prompt"] == action.action_data["prompt"]
    assert framework.sent


def test_config_examples_and_manifest_match_schema(framework):
    schema = framework.plugin.CONFIG_SCHEMA
    assert schema["plugin"]["config_version"].default == "2.3.0"
    assert schema["tag_retrieval"]["api_key"].input_type == "password"
    assert schema["tag_retrieval"]["api_key"].default == ""
    expected = {name: field.default for name, field in schema["tag_retrieval"].items()}
    for name in ("config_example.toml", "config.toml.example"):
        content = tomllib.loads((ROOT / name).read_text(encoding="utf-8"))
        assert content["tag_retrieval"] == expected
        assert content["plugin"]["config_version"] == "2.3.0"
    manifest = json.loads((ROOT / "_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "1.3.0"
    assert any(component["type"] == "tool" and component["name"] == "character_tag_lookup"
               for component in manifest["plugin_info"]["components"])
