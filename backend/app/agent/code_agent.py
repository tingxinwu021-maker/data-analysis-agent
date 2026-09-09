"""代码解释器编排：生成 pandas 代码 → 校验 → 沙箱执行 → 解释。

用于引擎 B（探索式分析）：对上传的 CSV/Excel 文件做统计、聚合等灵活分析。
"""
import re
import time
from pathlib import Path

import pandas as pd

from ..llm.client import chat
from ..observability import trace
from . import sandbox

PROJECT_ROOT = Path(__file__).resolve().parents[3]
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

MAX_RETRY = 1


def infer_schema(path: Path) -> dict:
    """读取文件，返回列名/类型/形状/前几行，供 LLM 生成代码时参考。"""
    df = _read_file(path)
    return {
        "columns": [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns],
        "shape": list(df.shape),
        "head_str": df.head(5).to_string(index=False),
    }


def _read_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)


def _resolve_upload(file_id: str) -> Path:
    """把 file_id 解析成 uploads 目录下的真实路径（防路径穿越）。"""
    path = UPLOAD_DIR / Path(file_id).name
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{file_id}")
    return path


def _extract_code(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r"```(?:python)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
    return raw.strip()


def _build_code_prompt(schema: dict, filename: str) -> str:
    cols = ", ".join(f"{c['name']}({c['dtype']})" for c in schema["columns"])
    head = schema["head_str"]
    return (
        "你是一个数据分析师，会用 pandas 分析数据文件并回答用户问题。\n\n"
        f"文件在【当前工作目录】下，文件名为：{filename}\n"
        f"列名与类型：{cols}\n"
        f"数据形状：{schema['shape'][0]} 行 x {schema['shape'][1]} 列\n"
        f"前 5 行：\n{head}\n\n"
        "## 任务\n"
        "写一段 Python 代码：读取该文件、做分析、用 print() 输出结果，回答用户问题。\n\n"
        "## 规则\n"
        "1. 只输出 Python 代码，不要任何解释，不要 markdown 代码块。\n"
        f"2. 读取文件用：df = pd.read_csv('{filename}')（或 pd.read_excel；文件名已给对，直接复制）。\n"
        "3. 只能 import pandas（和 numpy），不要 import 其他库。\n"
        "4. 用 print() 输出能直接回答问题的结果。\n"
        "5. 不要写文件、不要访问网络、不要读取其他路径、不要用 open()。\n"
        "6. 代码尽量简短。\n"
    )


def _generate_code(schema: dict, filename: str, question: str,
                   previous_error: str | None = None) -> str:
    system = _build_code_prompt(schema, filename)
    user = f"问题：{question}"
    if previous_error:
        user += f"\n\n上一次代码执行报错：\n{previous_error}\n请修正后重新只输出代码。"
    raw = chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,
    )
    return _extract_code(raw)


def _explain(question: str, code: str, stdout: str, stderr: str) -> str:
    err = f"\n执行报错：\n{stderr}" if stderr.strip() else ""
    user = (
        f"问题：{question}\n"
        f"代码：\n{code}\n"
        f"执行输出：\n{stdout}{err}\n\n"
        "请用 2-4 句简洁中文直接回答用户的问题。"
    )
    raw = chat(
        [{"role": "system", "content": "你是数据分析助手，用简洁中文解释分析结果。"},
         {"role": "user", "content": user}],
        temperature=0,
    )
    return raw.strip()


def analyze_path(path: Path, question: str) -> dict:
    """核心：对给定文件做代码解释式分析。"""
    t0 = time.time()
    schema = infer_schema(path)
    filename = path.name
    cwd = str(path.parent)

    code = _generate_code(schema, filename, question)
    ok, err = sandbox.validate_code(code)
    if not ok:
        return {"question": question, "code": code, "error": f"代码校验失败：{err}"}

    result = sandbox.run_code(code, cwd=cwd)
    if result["returncode"] != 0:
        code = _generate_code(schema, filename, question, previous_error=result["stderr"])
        ok, err = sandbox.validate_code(code)
        if not ok:
            return {"question": question, "code": code, "error": f"代码校验失败：{err}"}
        result = sandbox.run_code(code, cwd=cwd)

    explanation = _explain(question, code, result["stdout"], result["stderr"])
    trace.log_query(mode="code", question=question, file=filename,
                    returncode=result["returncode"],
                    error=result["stderr"] if result["returncode"] != 0 else None,
                    latency_ms=int((time.time() - t0) * 1000))
    return {
        "question": question,
        "file": filename,
        "code": code,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "returncode": result["returncode"],
        "timed_out": result["timed_out"],
        "explanation": explanation,
    }


def analyze(file_id: str, question: str) -> dict:
    """端点入口：按 file_id 分析（文件须先通过 /upload 上传）。"""
    path = _resolve_upload(file_id)
    return analyze_path(path, question)
