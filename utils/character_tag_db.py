"""角色标签数据库查询工具

纯 Python 实现，不依赖 MaiBot 的 src.* 模块，便于脱离 MaiBot 单独测试。

注意：utils/__init__.py 会导入其它依赖 MaiBot 的模块，因此本模块不要在
utils/__init__.py 中导出；命令文件请直接使用
`from ..utils.character_tag_db import ...` 导入。
"""
import base64
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 插件根目录（基于当前文件相对定位，禁止写死绝对路径）
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 角色数据库默认路径：<插件根>/data/character_tags.db
DEFAULT_DB_PATH = os.path.join(PLUGIN_ROOT, "data", "character_tags.db")
# 缩略图目录默认路径：<插件根>/thumbs
DEFAULT_THUMBS_DIR = os.path.join(PLUGIN_ROOT, "thumbs")

# 查询返回的字段
_RESULT_COLUMNS = ("name_cn", "copyright_cn", "trigger", "core_tags", "thumbname")

# 中英文逗号
_COMMA_PATTERN = re.compile(r"[,，]")


def parse_query(text: Optional[str]) -> Tuple[str, Optional[str]]:
    """解析用户输入的查询文本

    支持两种格式：
    - "角色名"：仅按角色名查询
    - "角色名,作品名"：中英文逗号均可，只在第一个逗号处分割一次

    Args:
        text: 用户输入（不含命令前缀）

    Returns:
        Tuple[str, Optional[str]]: (角色名, 作品名)。
            作品名为空或未提供时为 None。
            角色名为空字符串表示输入无效（调用方应提示用法）。
    """
    if not text:
        return "", None

    parts = _COMMA_PATTERN.split(text, maxsplit=1)
    name = parts[0].strip()
    if len(parts) == 1:
        return name, None

    copyright_name = parts[1].strip()
    return name, (copyright_name or None)


def escape_like(value: str) -> str:
    """转义 LIKE 通配符 % _ 以及转义符 \\，需配合 ESCAPE '\\' 使用"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _like_pattern(value: str) -> str:
    """生成"包含匹配"的 LIKE 参数"""
    return f"%{escape_like(value)}%"


def search_characters(
    db_path: str,
    name: str,
    copyright: Optional[str] = None,  # noqa: A002 - 与调用约定保持一致
    limit: int = 20,
) -> Tuple[int, List[Dict[str, Any]]]:
    """按角色名（可选作品名）模糊查询角色

    - 以只读 URI 方式打开数据库，不会修改也不会创建数据库文件
    - 所有用户输入均通过参数化查询传入，LIKE 通配符已转义
    - 结果按 count 降序排列，先 COUNT 总数再 LIMIT 取前 N 条

    Args:
        db_path: 数据库文件路径
        name: 角色名关键词（匹配 name_cn），不能为空
        copyright: 作品名关键词（匹配 copyright_cn），为空时不过滤
        limit: 最多返回的行数

    Returns:
        Tuple[int, List[Dict]]: (匹配总数, 前 limit 行)。
            每行为包含 name_cn / copyright_cn / trigger / core_tags / thumbname 的字典，
            NULL 值会被转换为空字符串。

    Raises:
        ValueError: 角色名为空
        FileNotFoundError: 数据库文件不存在
        sqlite3.Error: 数据库查询出错
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("角色名不能为空")
    copyright = (copyright or "").strip()
    # SQLite 中负数 LIMIT 表示不限制，这里统一钳制为非负
    limit = max(0, int(limit))

    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"角色数据库不存在: {path}")

    where = "name_cn LIKE ? ESCAPE '\\'"
    params: List[Any] = [_like_pattern(name)]
    if copyright:
        where += " AND copyright_cn LIKE ? ESCAPE '\\'"
        params.append(_like_pattern(copyright))

    columns = ", ".join(_RESULT_COLUMNS)
    # where / columns 均为本模块内的常量拼接，用户输入只走参数绑定
    count_sql = f"SELECT COUNT(*) FROM characters WHERE {where}"
    select_sql = (
        f"SELECT {columns} FROM characters WHERE {where} "
        "ORDER BY count DESC, character ASC LIMIT ?"
    )

    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        total = conn.execute(count_sql, params).fetchone()[0]
        if total == 0 or limit == 0:
            return total, []
        rows = conn.execute(select_sql, [*params, limit]).fetchall()
        results = [
            {col: ("" if row[col] is None else row[col]) for col in _RESULT_COLUMNS}
            for row in rows
        ]
    finally:
        conn.close()

    return total, results


def load_thumbnail_base64(thumbs_dir: str, thumbname: Optional[str]) -> Optional[str]:
    """读取缩略图并返回纯 base64 字符串（不带 data: 或 base64:// 前缀）

    只取文件名部分（防路径穿越），文件不存在或读取失败时返回 None。

    Args:
        thumbs_dir: 缩略图目录
        thumbname: 数据库中的缩略图文件名

    Returns:
        Optional[str]: base64 字符串；失败返回 None
    """
    if not thumbname or not isinstance(thumbname, str):
        return None

    # 同时兼容 / 与 \ 两种分隔符，避免在不同系统上被绕过
    safe_name = os.path.basename(thumbname.replace("\\", "/"))
    if safe_name in ("", ".", ".."):
        return None

    file_path = os.path.join(thumbs_dir, safe_name)
    if not os.path.isfile(file_path):
        return None

    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except OSError:
        return None

    if not data:
        return None
    return base64.b64encode(data).decode("ascii")
