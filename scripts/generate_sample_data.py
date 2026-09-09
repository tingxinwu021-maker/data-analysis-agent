"""生成「用户行为 / 产品分析」示例数据（确定性、可复现）。

产出：
  - data/raw/users.csv    用户维表
  - data/raw/events.csv   事件事实表
  - data/raw/sessions.csv 会话表（由事件聚合而来）
  - MySQL 库中的 users / events / sessions 三张表（落库到 MySQL）

运行：.venv\\Scripts\\python.exe scripts/generate_sample_data.py
"""
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 让脚本能以「项目根目录」运行并 import backend

from backend.app.db.connection import ensure_database, get_mysql_engine  # noqa: E402

RAW = ROOT / "data" / "raw"

random.seed(42)

N_USERS = 5000
START = date(2026, 6, 1)
DAYS = 90

COUNTRIES = ["CN", "US", "JP", "DE", "BR", "IN", "GB", "FR"]
DEVICES = ["ios", "android", "web", "desktop"]
PLANS = ["free", "pro", "enterprise"]
CHANNELS = ["organic", "ads", "referral", "email"]

# 事件名 + 权重：page_view 最频繁、purchase/signup 稀少，贴近真实
EVENT_NAMES = ["signup", "login", "page_view", "feature_used", "purchase", "invite_sent", "upgrade"]
EVENT_WEIGHTS = [1, 18, 40, 14, 1, 3, 1]
PAGES = ["home", "pricing", "dashboard", "settings", "docs", "blog"]
FEATURES = ["search", "export", "report", "share", "integrate", "api"]


def weighted_choice(population, weights):
    return random.choices(population, weights=weights, k=1)[0]


def random_day_time(day: date) -> datetime:
    return datetime(day.year, day.month, day.day,
                    random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))


def generate_users() -> pd.DataFrame:
    rows = []
    for uid in range(1, N_USERS + 1):
        rows.append({
            "user_id": uid,
            "signup_date": (START + timedelta(days=random.randint(0, DAYS - 1))).isoformat(),
            "country": weighted_choice(COUNTRIES, [30, 15, 10, 8, 8, 12, 9, 8]),
            "device": random.choice(DEVICES),
            "plan": weighted_choice(PLANS, [70, 25, 5]),
            "channel": weighted_choice(CHANNELS, [45, 25, 20, 10]),
        })
    return pd.DataFrame(rows)


def generate_events(users: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for uid, signup in zip(users["user_id"], users["signup_date"]):
        active_days = min(DAYS, 1 + int(random.expovariate(0.15)))
        for d in sorted(random.sample(range(DAYS), active_days)):
            day = START + timedelta(days=d)
            n_events = 1 + int(random.expovariate(0.2))
            session_id = f"{uid}-{day.isoformat()}"
            for _ in range(n_events):
                rows.append({
                    "event_id": len(rows) + 1,
                    "user_id": uid,
                    "event_name": weighted_choice(EVENT_NAMES, EVENT_WEIGHTS),
                    "event_time": random_day_time(day).isoformat(sep=" "),
                    "session_id": session_id,
                    "page": random.choice(PAGES),
                    "feature": random.choice(FEATURES),
                })
    return pd.DataFrame(rows)


def generate_sessions(events: pd.DataFrame) -> pd.DataFrame:
    g = events.groupby("session_id").agg(
        user_id=("user_id", "first"),
        started_at=("event_time", "min"),
        ended_at=("event_time", "max"),
    ).reset_index()
    g["duration_sec"] = (
        pd.to_datetime(g["ended_at"]) - pd.to_datetime(g["started_at"])
    ).dt.total_seconds().astype(int)
    return g


def load_to_mysql(users, events, sessions):
    """把三张表落库到 MySQL（显式指定日期/时间类型，避免被当成 TEXT）。"""
    from sqlalchemy import types as sa_types

    ensure_database()
    engine = get_mysql_engine()

    # 日期/时间列：字符串 → datetime64，并显式指定 SQLAlchemy 类型
    users["signup_date"] = pd.to_datetime(users["signup_date"])
    events["event_time"] = pd.to_datetime(events["event_time"])
    sessions["started_at"] = pd.to_datetime(sessions["started_at"])
    sessions["ended_at"] = pd.to_datetime(sessions["ended_at"])

    users.to_sql("users", con=engine, if_exists="replace", index=False,
                 dtype={"signup_date": sa_types.DATE()})
    events.to_sql("events", con=engine, if_exists="replace", index=False,
                  dtype={"event_time": sa_types.DATETIME()})
    sessions.to_sql("sessions", con=engine, if_exists="replace", index=False,
                    dtype={"started_at": sa_types.DATETIME(), "ended_at": sa_types.DATETIME()})
    return engine


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    users = generate_users()
    events = generate_events(users)
    sessions = generate_sessions(events)

    users.to_csv(RAW / "users.csv", index=False)
    events.to_csv(RAW / "events.csv", index=False)
    sessions.to_csv(RAW / "sessions.csv", index=False)

    engine = load_to_mysql(users, events, sessions)

    print("== 行数 ==")
    for t in ["users", "events", "sessions"]:
        n = pd.read_sql(f"SELECT count(*) AS n FROM `{t}`", engine)["n"][0]
        print(f"{t}: {n}")

    print("== 前 5 天 DAU（校验可查询）==")
    dau = pd.read_sql("""
        SELECT DATE(event_time) AS d, count(DISTINCT user_id) AS dau
        FROM events GROUP BY 1 ORDER BY 1 LIMIT 5
    """, engine)
    print(dau.to_string(index=False))
    print("done")


if __name__ == "__main__":
    main()
