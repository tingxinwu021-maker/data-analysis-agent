"""校验语义层 examples 中的 SQL 是否能在当前数据上正确执行。

这是 golden-SQL 回归测试的雏形（Phase 4 会扩展成完整评测集）。
运行：.venv\Scripts\python.exe scripts/validate_examples.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让脚本能以「项目根目录」运行并 import backend

from backend.app.agent.sql_agent import execute_sql  # noqa: E402
from backend.app.semantic.loader import load_semantic_layer  # noqa: E402


def main() -> int:
    sl = load_semantic_layer()
    failed = 0
    for ex in sl.examples:
        try:
            df = execute_sql(ex.sql)
            print(f"[OK]   {len(df)} rows | {ex.question}")
        except Exception as err:  # noqa: BLE001
            failed += 1
            print(f"[FAIL] {ex.question} -> {err}")
    print(f"\n{len(sl.examples) - failed}/{len(sl.examples)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
