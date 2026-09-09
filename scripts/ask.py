"""命令行测试入口（无前端时用它验证 agent）。

用法：.venv\\Scripts\\python.exe scripts/ask.py "最近7天每天的日活是多少？"
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.sql_agent import answer  # noqa: E402


def main() -> int:
    q = sys.argv[1] if len(sys.argv) > 1 else "最近7天每天的日活是多少？"
    print("问题：", q)
    result = answer(q)
    if result.get("error"):
        print("ERROR:", result["error"])
        print("SQL:", result.get("sql"))
        return 1
    print("SQL:", result["sql"])
    print("行数:", result["row_count"])
    print("解释:", result["explanation"])
    print("前 3 行:", json.dumps(result["rows"][:3], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
