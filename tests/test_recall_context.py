import asyncio
import importlib.util
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parent.parent


class Condition:
    def __init__(self, sql, values):
        self.sql = sql
        self.values = values

    def __and__(self, other):
        return Condition(f"({self.sql}) AND ({other.sql})", self.values + other.values)


class Field:
    def __init__(self, name):
        self.name = name

    def __eq__(self, value):
        return Condition(f'"{self.name}" IS ?', [value])

    def __ge__(self, value):
        return Condition(f'"{self.name}" >= ?', [value])

    def __le__(self, value):
        return Condition(f'"{self.name}" <= ?', [value])

    def __gt__(self, value):
        return Condition(f'"{self.name}" > ?', [value])


@pytest.fixture
def maibot_db(tmp_path, monkeypatch):
    connection = sqlite3.connect(tmp_path / "maibot.db")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY, message_id TEXT, chat_id TEXT, user_id TEXT,
            user_platform TEXT, user_nickname TEXT, time REAL, display_message TEXT,
            processed_plain_text TEXT, additional_config TEXT, is_picid INTEGER
        );
        CREATE TABLE action_records (
            action_id TEXT PRIMARY KEY, chat_id TEXT, time REAL, action_name TEXT,
            action_data TEXT, action_done INTEGER, action_build_into_prompt INTEGER,
            action_prompt_display TEXT, chat_info_platform TEXT
        );
        CREATE TABLE images (image_id TEXT PRIMARY KEY, description TEXT);
        """
    )

    def module(name, **attributes):
        result = ModuleType(name)
        result.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    def as_message(row):
        data = dict(row)
        return SimpleNamespace(
            **data,
            user_info=SimpleNamespace(
                user_id=data["user_id"],
                platform=data["user_platform"],
                user_nickname=data["user_nickname"],
                user_cardname=None,
            ),
            chat_info=SimpleNamespace(platform=data["user_platform"]),
        )

    def find_messages(message_filter, limit=0, **kwargs):
        conditions = [f'"{key}" IS ?' for key in message_filter]
        sql = "SELECT * FROM messages WHERE " + " AND ".join(conditions)
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = connection.execute(sql, list(message_filter.values())).fetchall()
        return [as_message(row) for row in rows]

    def recent_messages(chat_id, start_time, end_time, **kwargs):
        rows = connection.execute(
            "SELECT * FROM messages WHERE chat_id = ? AND time > ? AND time < ? ORDER BY time",
            (chat_id, start_time, end_time),
        ).fetchall()
        return [as_message(row) for row in rows]

    class UpdateQuery:
        def __init__(self, display_message):
            self.display_message = display_message
            self.condition = None

        def where(self, condition):
            self.condition = condition
            return self

        def execute(self):
            result = connection.execute(
                f"UPDATE messages SET display_message = ? WHERE {self.condition.sql}",
                [self.display_message, *self.condition.values],
            )
            connection.commit()
            return result.rowcount

    class Messages:
        id = Field("id")
        chat_id = Field("chat_id")
        message_id = Field("message_id")
        user_id = Field("user_id")
        display_message = Field("display_message")

        @classmethod
        def update(cls, display_message):
            return UpdateQuery(display_message)

    class ActionQuery:
        def __init__(self):
            self.condition = None
            self.order = None
            self.maximum = None

        def where(self, condition):
            self.condition = condition
            return self

        def order_by(self, field):
            self.order = field.name
            return self

        def limit(self, maximum):
            self.maximum = maximum
            return self

        def __iter__(self):
            sql = f"SELECT * FROM action_records WHERE {self.condition.sql}"
            if self.order:
                sql += f' ORDER BY "{self.order}"'
            if self.maximum:
                sql += f" LIMIT {int(self.maximum)}"
            return iter(SimpleNamespace(**dict(row)) for row in connection.execute(sql, self.condition.values))

    class ActionRecords:
        time = Field("time")
        chat_id = Field("chat_id")

        @classmethod
        def select(cls):
            return ActionQuery()

    class Images:
        image_id = Field("image_id")

        @classmethod
        def get_or_none(cls, condition):
            row = connection.execute(f"SELECT * FROM images WHERE {condition.sql}", condition.values).fetchone()
            return SimpleNamespace(**dict(row)) if row else None

    streams = {}

    async def store_action_info(**kwargs):
        stream = kwargs["chat_stream"]
        data = (
            kwargs["thinking_id"], stream.stream_id, time.time(), kwargs["action_name"],
            json.dumps(kwargs["action_data"], ensure_ascii=False), int(kwargs["action_done"]),
            int(kwargs["action_build_into_prompt"]), kwargs["action_prompt_display"], stream.platform,
        )
        connection.execute(
            "INSERT OR REPLACE INTO action_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", data
        )
        connection.commit()
        return {"action_id": data[0]}

    message_api = SimpleNamespace(get_messages_by_time_in_chat=recent_messages)
    database_api = SimpleNamespace(store_action_info=store_action_info)
    global_config = SimpleNamespace(
        bot=SimpleNamespace(qq_account="bot-1", platform="qq", nickname="机器人"),
        recall=SimpleNamespace(max_recall_time_limit=120),
    )
    module("src", __path__=[])
    module("src.config", __path__=[])
    module("src.config.config", global_config=global_config)
    module("src.plugin_system", __path__=[], BaseAction=object, BaseCommand=object,
           ActionActivationType=SimpleNamespace(ALWAYS="always"))
    module("src.plugin_system.apis", message_api=message_api, database_api=database_api)
    module("src.common", __path__=[])
    module("src.common.database", __path__=[])
    module("src.common.database.database_model", Messages=Messages, ActionRecords=ActionRecords, Images=Images)
    module("src.common.message_repository", find_messages=find_messages, count_messages=lambda *args, **kwargs: 0)
    module("src.chat", __path__=[])
    module("src.chat.message_receive", __path__=[])
    module("src.chat.message_receive.chat_stream", get_chat_manager=lambda: SimpleNamespace(get_stream=streams.get))

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        result = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, result)
        spec.loader.exec_module(result)
        return result

    manager = load("recall_context_manager", ROOT / "utils" / "recall_manager.py").RecallManager
    api_calls = []

    async def recall_api(url, message_id, token):
        api_calls.append((url, message_id, token))
        return True

    monkeypatch.setattr(manager, "_call_napcat_recall_api", recall_api)

    def add_message(chat_id, message_id, content="[图片：星空]", display_message="", user_id="bot-1", sent_at=None):
        streams.setdefault(chat_id, SimpleNamespace(stream_id=chat_id, platform="qq"))
        cursor = connection.execute(
            "INSERT INTO messages (message_id, chat_id, user_id, user_platform, user_nickname, time, "
            "display_message, processed_plain_text, additional_config, is_picid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(message_id), chat_id, user_id, "qq", "机器人", sent_at or time.time() - 5,
             display_message, content, "", 0),
        )
        connection.commit()
        return cursor.lastrowid

    def get_message(record_id):
        return dict(connection.execute("SELECT * FROM messages WHERE id = ?", (record_id,)).fetchone())

    def actions():
        return [dict(row) for row in connection.execute("SELECT * FROM action_records ORDER BY time")]

    yield SimpleNamespace(
        manager=manager, connection=connection, module=module, load=load, streams=streams,
        message_api=message_api, database_api=database_api, global_config=global_config,
        add_message=add_message, get_message=get_message, find_messages=find_messages,
        actions=actions, api_calls=api_calls,
    )
    connection.close()


def make_context(db, chat_id, message_id):
    context = {
        "timestamp": time.time() - 5,
        "stream_id": chat_id,
        "message_type": "image",
        "platform_message_id": int(message_id),
        "raw_message_id": str(message_id),
    }
    db.manager.track_sent_message(chat_id, context)
    return context


@pytest.mark.parametrize(
    "entry",
    ["automatic", "tracked_latest", "captured_latest", "latest", "action", "action_latest", "command", "command_latest"],
)
def test_successful_recall_updates_image_history_and_action(maibot_db, monkeypatch, entry):
    db = maibot_db
    message_pk = db.add_message("group-a", "101", content="[picid:sky]", display_message="")
    db.connection.execute("INSERT INTO images VALUES (?, ?)", ("sky", "星空画面"))
    db.connection.commit()

    if entry == "automatic":
        context = make_context(db, "group-a", "101")
        asyncio.run(db.manager.auto_recall_after_delay(0, "group-a", context, "http://napcat"))
        result = (context.get("recalled"),)
    elif entry in ("tracked_latest", "captured_latest"):
        context = make_context(db, "group-a", "101")
        if entry == "captured_latest":
            context.pop("platform_message_id")

            async def capture(chat_id, item, **kwargs):
                item["platform_message_id"] = 101
                return True

            monkeypatch.setattr(db.manager, "capture_sent_image", capture)
        result = asyncio.run(db.manager.recall_latest_image("group-a", "http://napcat"))
    elif entry == "latest":
        result = asyncio.run(db.manager.recall_latest_image("group-a", "http://napcat"))
    else:
        db.module("recall_test_plugin", __path__=[])
        db.module("recall_test_plugin.utils", RecallManager=db.manager)
        is_action = entry.startswith("action")
        component_name = "action" if is_action else "command"
        package = "actions" if is_action else "commands"
        db.module(f"recall_test_plugin.{package}", __path__=[])
        component = db.load(
            f"recall_test_plugin.{package}.recall_{component_name}", ROOT / package / f"recall_{component_name}.py"
        )
        instance = component.RecallAction() if is_action else component.RecallCommand()
        instance.get_config = lambda key, default=None: "http://napcat" if key == "recall.napcat_api_url" else default
        sent_text = []

        async def send_text(text):
            sent_text.append(text)

        instance.send_text = send_text
        reply_id = None if entry.endswith("_latest") else "101"
        if is_action:
            instance.chat_id = "group-a"
            instance.action_message = SimpleNamespace(reply_to=reply_id)
        else:
            instance.message = SimpleNamespace(chat_stream=db.streams["group-a"], reply_to=reply_id)
        result = asyncio.run(instance.execute())
        assert sent_text == ([] if is_action else ["已撤回该消息"])

    assert result[0] is True
    saved = db.get_message(message_pk)
    assert saved["display_message"] == "【该图片已撤回】[picid:sky]"
    assert saved["processed_plain_text"] == "[picid:sky]"
    assert len(db.actions()) == 1
    action = db.actions()[0]
    assert action["chat_id"] == "group-a"
    assert action["action_build_into_prompt"] == 1
    assert "[picid:sky]" in action["action_prompt_display"]
    assert json.loads(action["action_data"])["platform_message_id"] == "101"
    assert db.api_calls == [("http://napcat", 101, "")]


def test_scoped_recall_keeps_other_chat_and_other_image_unchanged(maibot_db):
    db = maibot_db
    target = db.add_message("group-a", "101", display_message="已生成的画面")
    other_image = db.add_message("group-a", "102")
    other_chat = db.add_message("group-b", "101")
    other_context = make_context(db, "group-b", "101")

    result = asyncio.run(db.manager.recall_by_message_id("101", "group-a", "http://napcat"))

    assert result[0] is True
    assert db.get_message(target)["display_message"] == "【该图片已撤回】已生成的画面"
    assert db.get_message(other_image)["display_message"] == ""
    assert db.get_message(other_chat)["display_message"] == ""
    assert not other_context.get("cancelled")
    assert [action["chat_id"] for action in db.actions()] == ["group-a"]


def test_recalled_image_is_skipped_after_restart_and_sync_is_idempotent(maibot_db, monkeypatch):
    db = maibot_db
    older = db.add_message("private-a", "101", sent_at=time.time() - 10)
    newer = db.add_message("private-a", "102", sent_at=time.time() - 5)
    assert asyncio.run(db.manager.recall_by_message_id("102", "private-a", "http://napcat"))[0]
    asyncio.run(db.manager._complete_recall("private-a", 102, "102", message=db.find_messages(
        {"chat_id": "private-a", "message_id": "102"}, limit=1
    )[0]))
    restarted_manager = db.load("recall_context_manager_restarted", ROOT / "utils" / "recall_manager.py").RecallManager
    monkeypatch.setattr(restarted_manager, "_call_napcat_recall_api", db.manager._call_napcat_recall_api)

    repeated = asyncio.run(restarted_manager.recall_by_message_id("102", "private-a", "http://napcat"))
    next_recall = asyncio.run(restarted_manager.recall_latest_image("private-a", "http://napcat"))

    assert repeated[0] is False and "已撤回" in repeated[1]
    assert next_recall[0] is True
    assert db.get_message(newer)["display_message"] == "【该图片已撤回】[图片：星空]"
    assert db.get_message(older)["display_message"] == "【该图片已撤回】[图片：星空]"
    assert len(db.actions()) == 2
    assert [call[1] for call in db.api_calls] == [102, 101]


def test_failed_platform_recall_does_not_change_history(maibot_db, monkeypatch):
    db = maibot_db
    message_pk = db.add_message("group-a", "101")
    context = make_context(db, "group-a", "101")

    async def fail_api(*args):
        return False

    monkeypatch.setattr(db.manager, "_call_napcat_recall_api", fail_api)
    result = asyncio.run(db.manager.recall_tracked_image("group-a", context, "http://napcat"))

    assert result[0] is False
    assert db.get_message(message_pk)["display_message"] == ""
    assert db.actions() == []
    assert not context.get("recalled")


def test_ambiguous_history_never_marks_either_message(maibot_db, caplog):
    db = maibot_db
    first = db.add_message("group-a", "101")
    second = db.add_message("group-a", "101")
    context = make_context(db, "group-a", "101")

    result = asyncio.run(db.manager.recall_tracked_image("group-a", context, "http://napcat"))

    assert result[0] is True
    assert db.get_message(first)["display_message"] == ""
    assert db.get_message(second)["display_message"] == ""
    assert "历史消息不唯一" in caplog.text
    assert len(db.actions()) == 1


def test_ambiguous_reply_is_rejected_before_platform_recall(maibot_db):
    db = maibot_db
    first = db.add_message("group-a", "101")
    second = db.add_message("group-a", "101")

    result = asyncio.run(db.manager.recall_by_message_id("101", "group-a", "http://napcat"))

    assert result[0] is False
    assert db.api_calls == []
    assert db.get_message(first)["display_message"] == ""
    assert db.get_message(second)["display_message"] == ""
    assert db.actions() == []


def test_missing_history_still_records_known_automatic_recall(maibot_db, caplog):
    db = maibot_db
    db.streams["group-a"] = SimpleNamespace(stream_id="group-a", platform="qq")
    context = make_context(db, "group-a", "101")

    result = asyncio.run(db.manager.recall_tracked_image("group-a", context, "http://napcat"))

    assert result[0] is True
    assert "无法唯一定位撤回图片的历史消息" in caplog.text
    assert len(db.actions()) == 1
    assert "101" in db.actions()[0]["action_prompt_display"]


@pytest.mark.parametrize("failure", ["history", "action"])
def test_sync_failure_does_not_misreport_platform_recall(maibot_db, monkeypatch, caplog, failure):
    db = maibot_db
    message_pk = db.add_message("group-a", "101")
    if failure == "history":
        def fail_history(*args):
            raise RuntimeError("历史记录不可写")

        monkeypatch.setattr(db.manager, "_mark_image_history_recalled", fail_history)
    else:
        async def fail_action(**kwargs):
            return None

        monkeypatch.setattr(db.database_api, "store_action_info", fail_action)

    result = asyncio.run(db.manager.recall_by_message_id("101", "group-a", "http://napcat"))

    assert result[0] is True
    if failure == "history":
        assert db.get_message(message_pk)["display_message"] == ""
        assert len(db.actions()) == 1
        assert "同步历史消息失败" in caplog.text
    else:
        assert db.get_message(message_pk)["display_message"].startswith("【该图片已撤回】")
        assert db.actions() == []
        assert "撤回动作记录保存失败" in caplog.text


def test_text_recall_does_not_create_image_marker(maibot_db):
    db = maibot_db
    message_pk = db.add_message("group-a", "101", content="绘图完成")

    result = asyncio.run(db.manager.recall_by_message_id("101", "group-a", "http://napcat"))

    assert result[0] is True
    assert db.get_message(message_pk)["display_message"] == ""
    assert db.actions() == []


@pytest.mark.parametrize("show_actions", [False, True])
@pytest.mark.parametrize("chat_id", ["group-a", "private-a"])
def test_maibot_history_builder_displays_recalled_image(maibot_db, show_actions, chat_id):
    db = maibot_db
    maibot_paths = (ROOT.parent / "MaiBot", ROOT.parent.parent)
    maibot_root = next((path for path in maibot_paths if (path / "src" / "chat" / "utils" / "chat_message_builder.py").is_file()), None)
    if maibot_root is None:
        pytest.skip("未找到 MaiBot 源码")

    db.add_message(chat_id, "101", content="[picid:sky]")
    db.connection.execute("INSERT INTO images VALUES (?, ?)", ("sky", "星空画面"))
    db.connection.commit()
    assert asyncio.run(db.manager.recall_by_message_id("101", chat_id, "http://napcat"))[0]

    db.module("src.common.data_models", __path__=[], BaseDataModel=type("BaseDataModel", (), {}))
    db.load("src.common.data_models.database_data_model", maibot_root / "src" / "common" / "data_models" / "database_data_model.py")
    db.load("src.common.data_models.message_data_model", maibot_root / "src" / "common" / "data_models" / "message_data_model.py")
    db.module("src.common.logger", get_logger=logging.getLogger)
    db.module("src.person_info", __path__=[])
    db.module("src.person_info.person_info", Person=lambda **kwargs: SimpleNamespace(person_name=""),
              get_person_id=lambda *args: "")
    db.module("src.chat.utils", __path__=[])
    db.module("src.chat.utils.utils", translate_timestamp_to_human_readable=lambda timestamp, mode: "时间",
              assign_message_ids=lambda messages: [])
    builder = db.load("maibot_history_builder_under_test", maibot_root / "src" / "chat" / "utils" / "chat_message_builder.py")

    messages = db.find_messages({"chat_id": chat_id, "message_id": "101"})
    output = builder.build_readable_messages(messages, show_actions=show_actions, truncate=True)

    assert "【该图片已撤回】[图片1]" in output
    assert "星空画面" in output
    assert ("你已撤回之前发送的图片" in output) is show_actions
