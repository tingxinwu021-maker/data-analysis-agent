"""数据源连接：MySQL（SQLAlchemy）。"""
from sqlalchemy import create_engine, text

from ..config import settings


def _url(database: str | None = None) -> str:
    """拼 MySQL 连接串；database 为空则连到 server（不选库），供建库用。"""
    db = database if database is not None else settings.mysql_database
    return (
        f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
        f"@{settings.mysql_host}:{settings.mysql_port}/{db}"
    )


def get_mysql_engine():
    """返回指向 mysql_database 的 SQLAlchemy 引擎。

    注意：正式查询时应使用只读账号，避免 LLM 生成的 SQL 误改数据。
    """
    return create_engine(_url(), pool_pre_ping=True)


def ensure_database() -> None:
    """创建目标数据库（若不存在）。供数据导入脚本建库使用。"""
    server = create_engine(_url(database=""))
    with server.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}`"))
    server.dispose()
