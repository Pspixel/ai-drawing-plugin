"""utils/character_tag_db.py 的单元测试

通过 importlib 按文件路径加载被测模块，避开 utils/__init__.py
（它会导入依赖 MaiBot 的其它模块，在单独测试环境下无法导入）。

运行方式（在插件根目录下）：
    python -m pytest tests -v
"""
import base64
import importlib.util
import sqlite3
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "utils" / "character_tag_db.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("character_tag_db_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


db = _load_module()

# 不含任何通配符的“普通”角色数据：(character, name_cn, copyright_cn, count, thumbname)
NORMAL_ROWS = [
    ("ganyu_(genshin_impact)", "甘雨 (原神)", "原神", 17983, "ganyu (genshin impact), genshin impact.webp"),
    ("ganyu_(twilight_blossom)", "甘雨 (玄玉瑶芳)", "原神", 399, "ganyu (twilight blossom), genshin impact.webp"),
    ("ganyu_(young)", "甘雨(幼年)", "原神", 131, "ganyu (young), genshin impact.webp"),
    ("ganyu_(fan_work)", "甘雨", "某同人作品", 50, "ganyu fan work.webp"),
    ("hatsune_miku", "初音未来", "VOCALOID", 90000, "miku, vocaloid.webp"),
    ("nahida", "纳西妲", "原神", 12000, "nahida's \"quote\", genshin.webp"),
]

# 名字中带有真正的 LIKE 通配符 / 转义符的数据，用来验证转义是否生效
WILDCARD_ROWS = [
    ("percent_char", "100%角色", "测试作品", 5, "percent.webp"),
    ("underscore_char", "key_角色", "测试作品", 4, "underscore.webp"),
    ("backslash_char", "反斜杠\\角色", "测试作品", 3, "backslash.webp"),
]


def _create_db(db_path: Path, rows) -> None:
    """按真实库的关键字段建一个最小的 characters 表"""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE characters (
                character    TEXT PRIMARY KEY,
                name_cn      TEXT,
                copyright_cn TEXT,
                trigger      TEXT NOT NULL DEFAULT '',
                core_tags    TEXT NOT NULL DEFAULT '',
                thumbname    TEXT NOT NULL DEFAULT '',
                count        INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.executemany(
            "INSERT INTO characters (character, name_cn, copyright_cn, trigger, core_tags, thumbname, count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (character, name_cn, copyright_cn, f"trigger of {character}", f"tags of {character}", thumb, count)
                for character, name_cn, copyright_cn, count, thumb in rows
            ],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "character_tags.db"
    _create_db(path, NORMAL_ROWS + WILDCARD_ROWS)
    return path


@pytest.fixture
def thumbs_dir(tmp_path):
    path = tmp_path / "thumbs"
    path.mkdir()
    return path


# ---------------------------------------------------------------- parse_query


class TestParseQuery:
    def test_only_name(self):
        assert db.parse_query("甘雨") == ("甘雨", None)

    def test_ascii_comma(self):
        assert db.parse_query("甘雨,原神") == ("甘雨", "原神")

    def test_chinese_comma(self):
        assert db.parse_query("甘雨，原神") == ("甘雨", "原神")

    def test_strip_spaces(self):
        assert db.parse_query("  甘雨  ,  原神  ") == ("甘雨", "原神")

    def test_split_only_once(self):
        # 第二个逗号属于作品名的一部分
        assert db.parse_query("甘雨,原神,国服") == ("甘雨", "原神,国服")
        assert db.parse_query("甘雨，原神，国服") == ("甘雨", "原神，国服")

    def test_empty_copyright_becomes_none(self):
        assert db.parse_query("甘雨,") == ("甘雨", None)
        assert db.parse_query("甘雨，  ") == ("甘雨", None)

    def test_empty_name_is_invalid(self):
        assert db.parse_query("") == ("", None)
        assert db.parse_query(None) == ("", None)
        assert db.parse_query("   ") == ("", None)
        assert db.parse_query(",原神") == ("", "原神")


# ---------------------------------------------------------------- search_characters


class TestSearchCharacters:
    def test_only_name(self, db_path):
        total, rows = db.search_characters(str(db_path), "甘雨")
        assert total == 4
        assert {r["name_cn"] for r in rows} == {"甘雨 (原神)", "甘雨 (玄玉瑶芳)", "甘雨(幼年)", "甘雨"}

    def test_result_fields(self, db_path):
        _, rows = db.search_characters(str(db_path), "初音")
        assert len(rows) == 1
        assert set(rows[0]) == {"name_cn", "copyright_cn", "trigger", "core_tags", "thumbname"}
        assert rows[0]["copyright_cn"] == "VOCALOID"
        assert rows[0]["thumbname"] == "miku, vocaloid.webp"

    def test_name_and_copyright_ascii_comma(self, db_path):
        name, copyright_name = db.parse_query("甘雨,原神")
        total, rows = db.search_characters(str(db_path), name, copyright_name)
        assert total == 3
        assert all(r["copyright_cn"] == "原神" for r in rows)

    def test_name_and_copyright_chinese_comma(self, db_path):
        name, copyright_name = db.parse_query("甘雨，原神")
        total, rows = db.search_characters(str(db_path), name, copyright_name)
        assert total == 3
        assert all(r["copyright_cn"] == "原神" for r in rows)

    def test_copyright_is_fuzzy(self, db_path):
        # 作品名也是包含匹配
        total, _ = db.search_characters(str(db_path), "甘雨", "同人")
        assert total == 1

    def test_no_result(self, db_path):
        assert db.search_characters(str(db_path), "不存在的角色") == (0, [])
        assert db.search_characters(str(db_path), "甘雨", "不存在的作品") == (0, [])

    def test_empty_copyright_is_ignored(self, db_path):
        total, _ = db.search_characters(str(db_path), "甘雨", "")
        assert total == 4

    def test_empty_name_raises(self, db_path):
        with pytest.raises(ValueError):
            db.search_characters(str(db_path), "   ")

    def test_limit_and_total(self, db_path):
        total, rows = db.search_characters(str(db_path), "甘雨", limit=2)
        assert total == 4  # total 是匹配总数，不受 limit 影响
        assert len(rows) == 2

    def test_limit_zero(self, db_path):
        total, rows = db.search_characters(str(db_path), "甘雨", limit=0)
        assert total == 4
        assert rows == []

    def test_negative_limit_does_not_mean_unlimited(self, db_path):
        # SQLite 的负数 LIMIT 表示不限制，模块应将其钳制为 0
        total, rows = db.search_characters(str(db_path), "甘雨", limit=-1)
        assert total == 4
        assert rows == []

    def test_order_by_count_desc(self, db_path):
        _, rows = db.search_characters(str(db_path), "甘雨", limit=10)
        assert [r["name_cn"] for r in rows] == ["甘雨 (原神)", "甘雨 (玄玉瑶芳)", "甘雨(幼年)", "甘雨"]

    def test_limit_keeps_highest_count(self, db_path):
        _, rows = db.search_characters(str(db_path), "甘雨", limit=1)
        assert rows[0]["name_cn"] == "甘雨 (原神)"

    def test_null_values_become_empty_string(self, tmp_path):
        path = tmp_path / "null.db"
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE characters (character TEXT PRIMARY KEY, name_cn TEXT, copyright_cn TEXT, "
            "trigger TEXT, core_tags TEXT, thumbname TEXT, count INTEGER)"
        )
        conn.execute("INSERT INTO characters VALUES ('a', '空值角色', '作品', NULL, NULL, NULL, 1)")
        conn.commit()
        conn.close()

        _, rows = db.search_characters(str(path), "空值")
        assert rows[0]["trigger"] == ""
        assert rows[0]["core_tags"] == ""
        assert rows[0]["thumbname"] == ""

    def test_db_missing_raises_and_is_not_created(self, tmp_path):
        missing = tmp_path / "not_exist.db"
        with pytest.raises(FileNotFoundError):
            db.search_characters(str(missing), "甘雨")
        assert not missing.exists()  # 只读模式，不应顺手创建空库

    def test_path_with_special_characters(self, tmp_path):
        # 路径含空格、#、% 时，as_uri() 的百分号编码必须正确
        special_dir = tmp_path / "dir with space #1 100%"
        special_dir.mkdir()
        path = special_dir / "角色 库.db"
        _create_db(path, NORMAL_ROWS)

        total, _ = db.search_characters(str(path), "甘雨")
        assert total == 4

    def test_connection_is_read_only(self, db_path):
        # 查询后库内容保持不变，且只读连接无法写入
        before = db_path.read_bytes()
        db.search_characters(str(db_path), "甘雨")
        assert db_path.read_bytes() == before

        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("DELETE FROM characters")
        finally:
            conn.close()


class TestLikeEscape:
    def test_percent_does_not_match_all(self, db_path):
        # 输入 "%" 只应匹配名字里真的含 "%" 的那一行，而不是全部
        total, rows = db.search_characters(str(db_path), "%")
        assert total == 1
        assert rows[0]["name_cn"] == "100%角色"

    def test_underscore_does_not_match_any_char(self, db_path):
        # "_" 若未转义会匹配任意单字符 => 命中全部；转义后只命中含下划线的行
        total, rows = db.search_characters(str(db_path), "_")
        assert total == 1
        assert rows[0]["name_cn"] == "key_角色"

    def test_underscore_in_middle(self, db_path):
        # "y_角" 未转义时也会匹配 "y?角"；这里确认精确匹配
        total, _ = db.search_characters(str(db_path), "key_角")
        assert total == 1

    def test_backslash_is_literal(self, db_path):
        total, rows = db.search_characters(str(db_path), "\\")
        assert total == 1
        assert rows[0]["name_cn"] == "反斜杠\\角色"

    def test_wildcard_in_copyright(self, db_path):
        total, _ = db.search_characters(str(db_path), "角色", "%")
        assert total == 0

    def test_escape_like_function(self):
        assert db.escape_like("a%b_c\\d") == "a\\%b\\_c\\\\d"

    def test_sql_injection_text_is_just_text(self, db_path):
        total, _ = db.search_characters(str(db_path), "' OR '1'='1")
        assert total == 0
        # 表仍然完整
        total_all, _ = db.search_characters(str(db_path), "角色")
        assert total_all >= 3


# ---------------------------------------------------------------- load_thumbnail_base64


class TestLoadThumbnail:
    def test_load_existing(self, thumbs_dir):
        data = b"RIFF\x00\x00\x00\x00WEBPVP8 fake-bytes"
        (thumbs_dir / "a.webp").write_bytes(data)

        result = db.load_thumbnail_base64(str(thumbs_dir), "a.webp")
        assert result == base64.b64encode(data).decode("ascii")
        assert not result.startswith(("base64://", "data:"))
        assert base64.b64decode(result) == data

    def test_filename_with_special_chars(self, thumbs_dir):
        # 真实缩略图文件名含空格、括号、逗号、单引号
        name = "ganyu (genshin impact), nahida's genshin.webp"
        (thumbs_dir / name).write_bytes(b"x")
        assert db.load_thumbnail_base64(str(thumbs_dir), name) is not None

    def test_missing_file(self, thumbs_dir):
        assert db.load_thumbnail_base64(str(thumbs_dir), "missing.webp") is None

    def test_empty_or_invalid_thumbname(self, thumbs_dir):
        assert db.load_thumbnail_base64(str(thumbs_dir), "") is None
        assert db.load_thumbnail_base64(str(thumbs_dir), None) is None
        assert db.load_thumbnail_base64(str(thumbs_dir), "..") is None
        assert db.load_thumbnail_base64(str(thumbs_dir), ".") is None

    def test_directory_is_not_a_file(self, thumbs_dir):
        (thumbs_dir / "sub.webp").mkdir()
        assert db.load_thumbnail_base64(str(thumbs_dir), "sub.webp") is None

    def test_empty_file_returns_none(self, thumbs_dir):
        (thumbs_dir / "empty.webp").write_bytes(b"")
        assert db.load_thumbnail_base64(str(thumbs_dir), "empty.webp") is None

    def test_path_traversal_forward_slash(self, tmp_path, thumbs_dir):
        # 目录外放一个“机密”文件，../ 穿越不应读到
        (tmp_path / "secret.txt").write_bytes(b"secret")
        assert db.load_thumbnail_base64(str(thumbs_dir), "../secret.txt") is None
        assert db.load_thumbnail_base64(str(thumbs_dir), "../../secret.txt") is None

    def test_path_traversal_backslash(self, tmp_path, thumbs_dir):
        (tmp_path / "secret.txt").write_bytes(b"secret")
        assert db.load_thumbnail_base64(str(thumbs_dir), "..\\secret.txt") is None

    def test_absolute_path_is_reduced_to_basename(self, tmp_path, thumbs_dir):
        outside = tmp_path / "outside.webp"
        outside.write_bytes(b"outside")
        # 传入绝对路径时只取文件名，在 thumbs 目录下找不到 => None
        assert db.load_thumbnail_base64(str(thumbs_dir), str(outside)) is None

    def test_traversal_prefix_falls_back_to_basename_inside_dir(self, thumbs_dir):
        # "../x.webp" 会被缩减为 "x.webp"，只会读取 thumbs 目录内的同名文件
        (thumbs_dir / "x.webp").write_bytes(b"inside")
        result = db.load_thumbnail_base64(str(thumbs_dir), "../x.webp")
        assert base64.b64decode(result) == b"inside"


# ---------------------------------------------------------------- 路径常量


def test_default_paths_are_relative_to_plugin_root():
    plugin_root = MODULE_PATH.parent.parent
    assert Path(db.PLUGIN_ROOT) == plugin_root
    assert Path(db.DEFAULT_DB_PATH) == plugin_root / "data" / "character_tags.db"
    assert Path(db.DEFAULT_THUMBS_DIR) == plugin_root / "thumbs"
