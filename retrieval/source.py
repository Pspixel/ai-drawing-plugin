"""角色数据源适配器，通用索引不依赖角色表结构。"""
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PLUGIN_ROOT / "data" / "character_tags.db"
DEFAULT_INDEX_PATH = PLUGIN_ROOT / "data" / "character_vectors.npz"


@dataclass(frozen=True)
class TagRecord:
    source: str
    record_id: str
    text: str
    payload: dict[str, str]


def _connect(path: Path) -> sqlite3.Connection:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError("角色标签库不存在")
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _record(row: sqlite3.Row) -> TagRecord:
    payload = {key: str(row[key] or "") for key in (
        "name_cn", "copyright_cn", "trigger", "core_tags",
    )}
    text = (
        f"角色：{payload['name_cn']}；英文标识：{row['character']}；"
        f"作品：{payload['copyright_cn']}；触发标签：{payload['trigger']}；"
        f"核心外观：{payload['core_tags']}"
    )
    return TagRecord("character", str(row["character"]), text, payload)


def load_characters(db_path: Path) -> tuple[list[TagRecord], str]:
    """在同一只读快照中生成语料和内容指纹，包含记录顺序与所有返回字段。"""
    connection = _connect(db_path)
    try:
        records = [_record(row) for row in connection.execute(
            "SELECT character, name_cn, copyright_cn, trigger, core_tags "
            "FROM characters ORDER BY character"
        )]
    finally:
        connection.close()
    digest = hashlib.sha256()
    for record in records:
        digest.update(json.dumps(
            [record.source, record.record_id, record.text, record.payload],
            ensure_ascii=False, sort_keys=True,
        ).encode("utf-8"))
        digest.update(b"\n")
    return records, digest.hexdigest()


def search_names(db_path: Path, name: str, copyright: str = "", limit: int = 30) -> list[TagRecord]:
    """保留原名称包含匹配策略，并补充英文标识、触发词匹配，不改变 /chartag。"""
    def pattern(value):
        return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"

    where = "(name_cn LIKE ? ESCAPE '\\' OR character LIKE ? ESCAPE '\\' OR trigger LIKE ? ESCAPE '\\')"
    params = [pattern(name)] * 3
    if copyright:
        where += " AND copyright_cn LIKE ? ESCAPE '\\'"
        params.append(pattern(copyright))
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            "SELECT character, name_cn, copyright_cn, trigger, core_tags FROM characters WHERE "
            + where + " ORDER BY count DESC, character ASC LIMIT ?",
            [*params, max(0, int(limit))],
        ).fetchall()
        return [_record(row) for row in rows]
    finally:
        connection.close()
