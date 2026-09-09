"""从 MySQL 读取表结构，自动更新 semantic.yaml 的 models 段。

只重写 models（表名/字段/类型，并把 MySQL 的列注释、表注释当作 description），
保留 version / metrics / examples 与顶部注释不动；对引用了已不存在表名的
指标与示例打印警告，供人工跟进。

用法：
  .venv\Scripts\python.exe scripts\export_mysql_schema.py            # 改写（自动备份 .bak）
  .venv\Scripts\python.exe scripts\export_mysql_schema.py --dry-run  # 只打印，不写文件
"""
import argparse
import re
import sys
from pathlib import Path

import yaml
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让脚本能以「项目根目录」运行并 import backend

from backend.app.db.connection import get_mysql_engine  # noqa: E402
from backend.app.semantic.loader import SemanticLayer, load_semantic_layer  # noqa: E402

SEMANTIC_FILE = ROOT / "semantic" / "semantic.yaml"

# MySQL data_type → 语义层类型（粗粒度，够 LLM 理解即可；未知类型兜底 varchar）
TYPE_MAP = {
    "tinyint": "integer", "smallint": "integer", "mediumint": "integer",
    "int": "integer", "integer": "integer", "bigint": "integer",
    "decimal": "decimal", "numeric": "decimal",
    "float": "float", "double": "float", "real": "float",
    "date": "date", "datetime": "timestamp", "timestamp": "timestamp",
    "time": "time", "year": "integer",
    "char": "varchar", "varchar": "varchar",
    "tinytext": "varchar", "text": "varchar",
    "mediumtext": "varchar", "longtext": "varchar",
    "enum": "varchar", "set": "varchar",
    "json": "json", "boolean": "boolean", "bool": "boolean",
    "binary": "varchar", "varbinary": "varchar", "blob": "varchar",
}


def map_type(mysql_type: str) -> str:
    """把 MySQL data_type 映射成语义层的粗粒度类型。"""
    return TYPE_MAP.get(str(mysql_type).lower(), "varchar")


def fetch_tables(engine) -> dict[str, dict]:
    """读取当前库所有 BASE TABLE 的表名/注释/列/类型，按表聚合。"""
    sql = text("""
        SELECT t.table_name AS table_name, t.table_comment AS table_comment,
               c.column_name AS column_name, c.data_type AS data_type,
               c.column_comment AS column_comment, c.ordinal_position AS ordinal_position
        FROM information_schema.tables t
        JOIN information_schema.columns c
          ON c.table_schema = t.table_schema AND c.table_name = t.table_name
        WHERE t.table_schema = DATABASE() AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name, c.ordinal_position
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()

    tables: dict[str, dict] = {}
    for r in rows:
        tname = r.table_name
        if tname not in tables:
            tables[tname] = {"description": (r.table_comment or "").strip(), "columns": []}
        tables[tname]["columns"].append({
            "name": r.column_name,
            "type": map_type(r.data_type),
            "description": (r.column_comment or "").strip(),
        })
    return tables


def build_models(tables: dict[str, dict], sl: SemanticLayer) -> list[dict]:
    """生成新 models，并继承旧语义层里的 synonyms 与手写 description。

    结构真相（表/列/类型）以 MySQL 为准；语义增强（synonyms、DB 未提供注释时的
    description）按 (表名, 列名) 从旧 yaml 继承，避免重跑时丢掉手写资产。
    """
    old_cols = {(m.name, c.name): c for m in sl.models for c in m.columns}
    old_tbls = {m.name: m for m in sl.models}

    models = []
    for tname, info in tables.items():
        old_tbl = old_tbls.get(tname)
        cols = []
        for col in info["columns"]:
            old_col = old_cols.get((tname, col["name"]))
            # description：DB 列注释优先；DB 没注释则回退旧手写描述
            desc = (col["description"] or (old_col.description if old_col else "")).strip()
            # synonyms：MySQL 里没有落点，永远从旧 yaml 继承
            syns = list(old_col.synonyms) if old_col else []
            new_col = {"name": col["name"], "type": col["type"], "description": desc}
            if syns:
                new_col["synonyms"] = syns
            cols.append(new_col)

        table_desc = (info["description"] or (old_tbl.description if old_tbl else "")).strip()
        models.append({"name": tname, "description": table_desc, "columns": cols})
    return models


def _top_level_key_index(lines: list[str], start: int) -> int:
    """返回从 start 起第一个顶层 key 的行号；找不到返回 len(lines)。"""
    for i in range(start, len(lines)):
        stripped = lines[i].strip()
        if (stripped and not stripped.startswith("#")
                and not lines[i][0].isspace() and stripped.endswith(":")):
            return i
    return len(lines)


def replace_models_block(new_models: list[dict]) -> str:
    """只替换 semantic.yaml 里的 models 列表，保留其它内容与注释。"""
    lines = SEMANTIC_FILE.read_text(encoding="utf-8").splitlines()
    models_idx = next(i for i, l in enumerate(lines) if l.strip() == "models:")

    # 找 models: 之后的下一个段落分隔线（# ===== ...），保留它及其后的 metrics/examples
    next_idx = len(lines)
    for i in range(models_idx + 1, len(lines)):
        if lines[i].strip().startswith("# ====="):
            next_idx = i
            break
    if next_idx == len(lines):
        # 兜底：没有段落分隔线时，退回到下一个顶层 key
        next_idx = _top_level_key_index(lines, models_idx + 1)

    # 生成 models 列表 YAML，并整体缩进 2 格（作为 models: 键的值）
    dumped = yaml.safe_dump(new_models, allow_unicode=True, sort_keys=False,
                            default_flow_style=False)
    indented = "\n".join(("  " + l) if l else l for l in dumped.splitlines())

    return "\n".join(lines[:models_idx + 1] + indented.splitlines() + lines[next_idx:]) + "\n"


def warn_stale(sl: SemanticLayer, new_table_names: set[str]) -> None:
    """提示引用了已不存在表名的指标/示例。"""
    old_names = {m.name for m in sl.models}
    stale = old_names - new_table_names
    if not stale:
        return
    for m in sl.metrics:
        if m.entity and m.entity in stale:
            print(f"  [警告] 指标 {m.name} 的 entity={m.entity} 已不在新 schema，需人工更新")
    for ex in sl.examples:
        used = {t for t in old_names if re.search(rf"\b{t}\b", ex.sql)}
        gone = used & stale
        if gone:
            print(f"  [警告] 示例「{ex.question}」引用了已移除的表 {sorted(gone)}，需人工更新")


def main() -> int:
    parser = argparse.ArgumentParser(description="从 MySQL 读取表结构，更新 semantic.yaml 的 models 段")
    parser.add_argument("--dry-run", action="store_true", help="只打印将写入的内容，不修改文件")
    args = parser.parse_args()

    sl = load_semantic_layer()  # 现有语义层（用于 stale 警告）
    engine = get_mysql_engine()
    db_name = engine.url.database
    tables = fetch_tables(engine)
    engine.dispose()

    if not tables:
        print("当前库没有发现任何表（BASE TABLE）。")
        return 1

    new_models = build_models(tables, sl)
    new_text = replace_models_block(new_models)

    print(f"读取库：{db_name}")
    print(f"发现 {len(tables)} 张表：")
    for tname, info in tables.items():
        print(f"  - {tname}（{len(info['columns'])} 列）")

    new_names = {t["name"] for t in new_models}
    warn_stale(sl, new_names)

    if args.dry_run:
        print("\n===== 将写入的 models 段（dry-run，未写文件）=====")
        print(yaml.safe_dump(new_models, allow_unicode=True, sort_keys=False,
                             default_flow_style=False))
        return 0

    # 写入前先校验新内容能被语义层正确解析
    SemanticLayer(**yaml.safe_load(new_text))

    bak = SEMANTIC_FILE.parent / (SEMANTIC_FILE.name + ".bak")
    bak.write_text(SEMANTIC_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    SEMANTIC_FILE.write_text(new_text, encoding="utf-8")
    print(f"\n已更新 {SEMANTIC_FILE.name}（原文件备份到 {bak.name}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
