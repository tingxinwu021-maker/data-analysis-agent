"""受限代码执行沙箱（本地 subprocess，非 Docker 级隔离）。

接口保持 run_code(code) 不变，生产环境可直接替换为 Docker / E2B 实现，不动上层。
"""
import re
import subprocess
import sys

# 危险导入/调用：出现即拒绝（启发式护栏，不是 Docker 级隔离，可被绕过）
FORBIDDEN = re.compile(
    r"\bimport\s+(os|sys|subprocess|socket|shutil|pathlib|glob|requests|urllib|"
    r"http|ftplib|pickle|ctypes|importlib|multiprocessing|webbrowser)\b"
    r"|\bfrom\s+(os|sys|subprocess|socket|shutil|pathlib|requests|urllib|pickle|"
    r"ctypes|importlib|multiprocessing)\s+import\b"
    r"|\b(eval|exec|compile|__import__|open|input|exit|quit|breakpoint)\s*\(",
    re.IGNORECASE,
)

DEFAULT_TIMEOUT = 30


def validate_code(code: str) -> tuple[bool, str]:
    """最佳努力的静态检查：拦截明显的危险 import / 调用。"""
    if not code.strip():
        return False, "代码为空"
    if FORBIDDEN.search(code):
        return False, "代码包含被禁止的 import 或函数调用"
    return True, ""


def run_code(code: str, timeout: int = DEFAULT_TIMEOUT, cwd: str | None = None) -> dict:
    """在独立子进程里执行 Python 代码，捕获 stdout/stderr，超时杀进程。

    -I：隔离模式（忽略环境变量与用户 site-packages），减少注入面。
    -X utf8：强制子进程以 UTF-8 输出，避免中文乱码。
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"执行超时（>{timeout} 秒），已终止",
            "returncode": -1,
            "timed_out": True,
        }
