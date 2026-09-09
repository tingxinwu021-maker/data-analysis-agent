"""命令行测试代码解释器。

用法：.venv\\Scripts\\python.exe scripts/analyze.py data/raw/users.csv "按 plan 统计用户数"
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agent.code_agent import analyze_path  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print('用法：python scripts/analyze.py <文件路径> "问题"')
        return 2
    path = Path(sys.argv[1])
    question = sys.argv[2]
    if not path.exists():
        print("文件不存在：", path)
        return 1

    result = analyze_path(path, question)
    if result.get("error"):
        print("ERROR:", result["error"])
        print("CODE:\n", result.get("code"))
        return 1

    print("CODE:\n", result["code"])
    print("--- 执行输出 ---")
    print(result["stdout"], end="")
    if result["stderr"].strip():
        print("--- stderr ---")
        print(result["stderr"])
    print("--- 解释 ---")
    print(result["explanation"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
