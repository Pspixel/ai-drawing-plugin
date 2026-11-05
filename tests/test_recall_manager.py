import asyncio
import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def recall_manager(monkeypatch):
    def module(name, **attributes):
        result = ModuleType(name)
        result.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    message_api = SimpleNamespace(get_messages_by_time_in_chat=lambda **kwargs: [])
    module("src", __path__=[])
    module("src.config", __path__=[])
    module(
        "src.config.config",
        global_config=SimpleNamespace(
            bot=SimpleNamespace(qq_account="bot-1"),
            recall=SimpleNamespace(max_recall_time_limit=120),
        ),
    )
    module("src.plugin_system", __path__=[])
    module("src.plugin_system.apis", message_api=message_api)

    module_name = "recall_manager_under_test"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "utils" / "recall_manager.py")
    imported = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, imported)
    spec.loader.exec_module(imported)
    return SimpleNamespace(manager=imported.RecallManager, message_api=message_api)


def test_group_auto_recall_modes_match_string_and_integer_ids(recall_manager):
    manager = recall_manager.manager

    assert manager.should_auto_recall_group(123, "whitelist", ["123"]) is False
    assert manager.should_auto_recall_group("456", "whitelist", [123]) is True
    assert manager.should_auto_recall_group("123", "blacklist", [123]) is True
    assert manager.should_auto_recall_group(456, "blacklist", ["123"]) is False
    assert manager.should_auto_recall_group(123, "whitelist", []) is True
    assert manager.should_auto_recall_group(123, "blacklist", []) is False


def test_recent_recall_target_never_falls_back_to_bot_text(recall_manager):
    manager = recall_manager.manager
    bot_text = {"sender_type": "bot", "time": 2, "processed_plain_text": "绘图已完成"}
    bot_image = {"sender_type": "bot", "time": 1, "is_picid": True}

    assert manager._pick_recall_target([bot_text], None, prefer_image=True) is None
    assert manager._pick_recall_target([bot_text, bot_image], None, prefer_image=True) is bot_image


def test_consecutive_images_keep_separate_platform_ids(recall_manager):
    manager = recall_manager.manager
    now = time.time()
    messages = []
    recall_manager.message_api.get_messages_by_time_in_chat = lambda **kwargs: list(messages)

    first = manager.begin_sent_image("chat", "stream", timestamp=now)
    first_message = {
        "message_id": "101",
        "time": now + 0.001,
        "sender_type": "bot",
        "is_picid": True,
    }
    messages.append(first_message)
    first["send_completed_at"] = now + 0.01

    second = manager.begin_sent_image("chat", "stream", timestamp=now + 0.02)
    second_message = {
        "message_id": "202",
        "time": now + 0.021,
        "sender_type": "bot",
        "is_picid": True,
    }
    messages.append(second_message)
    second["send_completed_at"] = now + 0.03

    assert asyncio.run(manager.capture_sent_image("chat", first, wait_timeout=0.1))
    assert asyncio.run(manager.capture_sent_image("chat", second, wait_timeout=0.1))
    assert first["platform_message_id"] == 101
    assert second["platform_message_id"] == 202


def test_ambiguous_image_target_is_skipped(recall_manager, monkeypatch):
    manager = recall_manager.manager
    now = time.time()
    messages = []
    recall_manager.message_api.get_messages_by_time_in_chat = lambda **kwargs: list(messages)
    context = manager.begin_sent_image("chat", "stream", timestamp=now)
    context["send_completed_at"] = now + 0.01
    messages.extend(
        [
            {"message_id": "101", "time": now + 0.001, "sender_type": "bot", "is_picid": True},
            {"message_id": "202", "time": now + 0.002, "sender_type": "bot", "is_picid": True},
        ]
    )

    called = []

    async def recall_api(*args, **kwargs):
        called.append(args)
        return True

    monkeypatch.setattr(manager, "_call_napcat_recall_api", recall_api)
    success, message = asyncio.run(
        manager.recall_tracked_image("chat", context, "http://napcat", max_recall_time_limit=120)
    )

    assert success is False
    assert "无法唯一确认" in message
    assert called == []


def test_recall_unknown_message_id_is_rejected(recall_manager, monkeypatch):
    manager = recall_manager.manager
    monkeypatch.setattr(manager, "get_message_by_id", lambda message_id, chat_id: None)
    called = []

    async def recall_api(*args, **kwargs):
        called.append(args)
        return True

    monkeypatch.setattr(manager, "_call_napcat_recall_api", recall_api)
    success, message = asyncio.run(
        manager.recall_by_message_id("987654321", "chat", "http://napcat", max_recall_time_limit=120)
    )

    assert success is False
    assert "未找到目标消息" in message
    assert called == []


def test_manual_recall_cancels_matching_auto_recall(recall_manager, monkeypatch):
    manager = recall_manager.manager
    context = {"timestamp": time.time(), "platform_message_id": 987654321}
    manager.track_sent_message("chat", context)
    message = {
        "message_id": "987654321",
        "time": time.time(),
        "sender_type": "bot",
        "user_id": "bot-1",
    }
    monkeypatch.setattr(manager, "get_message_by_id", lambda message_id, chat_id: message)

    async def recall_api(*args, **kwargs):
        return True

    monkeypatch.setattr(manager, "_call_napcat_recall_api", recall_api)
    success, _ = asyncio.run(manager.recall_by_message_id("987654321", "chat", "http://napcat"))

    assert success is True
    assert context["cancelled"] is True
    assert context["recalled"] is True
    assert manager._recent_messages["chat"] == []
