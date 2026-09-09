"""全局配置：从 .env 读取，pydantic-settings 自动映射环境变量。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- LLM（DeepSeek，OpenAI 兼容接口） ----------
    llm_provider: str = "deepseek"
    llm_api_key: str = "sk-REPLACE_ME"  # 占位符，请在 .env 中替换
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    # ---------- 数据源（MySQL） ----------
    # 建议为 LLM 查询建一个只读账号，避免生成的 SQL 误改数据。
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "analytics_demo"


settings = Settings()
