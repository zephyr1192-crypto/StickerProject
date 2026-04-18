import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "python:trend.scorer:v1.0"
    data_source_mode: str = "FREE_API"
    sticker_limit: int = 5
    input_file: str = "hn_trends_analyzed.csv"
    output_dir: str = "stickers_output"

    # Printful API連携用
    printful_api_key: str = ""
    printful_store_id: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = AppSettings()