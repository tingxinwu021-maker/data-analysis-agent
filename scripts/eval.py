"""golden-SQL 回归评测。

对 eval/cases.yaml 里的每个用例，让 agent 生成 SQL 并执行，
与 golden SQL 的执行结果对比（比较列名 + 行内容，行序/列序无关）。

运行：.venv\\Scripts\\python.exe scripts/eval.py
"""
import datetime as dt
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.sql_agent import execute_sql, query  # noqa: E402

CASES_FILE = ROOT / "eval" / "cases.yaml"


def _cell(v):
    """把一个单元格归一化成可比较的值。"""
    if v is None:
        return None
    try:
        import numpy as np
        if isinstance(v, np.generic):
            v = v.item()
    except ImportError:
        pass
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (int, str)):
        return v
    return str(v)


def _norm(df):
    cols = sorted(df.columns.tolist())
    rows = sorted(tuple(_cell(row[c]) for c in cols) for row in df.to_dict("records"))
    return cols, rows


def results_equal(a, b) -> bool:
    ca, ra = _norm(a)
    cb, rb = _norm(b)
    return ca == cb and ra == rb


def main() -> int:
    cases = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))["cases"]
    passed = 0
    for i, c in enumerate(cases, 1):
        q = c["question"]
        try:
            golden_df = execute_sql(c["sql"].strip())
        except Exception as e:  # noqa: BLE001
            print(f"[ERR ] {q} -> golden SQL 执行失败: {e}")
            continue

        r = query(q)
        if "error" in r:
            print(f"[FAIL] {q} -> {r['error']}")
            continue

        if results_equal(golden_df, r["df"]):
            passed += 1
            print(f"[PASS] {q}")
        else:
            print(f"[FAIL] {q}")
            print(f"  golden head: {golden_df.head(3).to_dict('records')}")
            print(f"  actual head: {r['df'].head(3).to_dict('records')}")

    print(f"\n{passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
