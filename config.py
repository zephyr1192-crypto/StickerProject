from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    # Reddit関連 (将来用)
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = ""
    
    # 画像生成関連 (デフォルト値)
    limit: int = 5
    input_file: str = "hn_trends_analyzed.csv"
    output_dir: str = "stickers_output"

    # Printful API連携用
    printful_api_key: str = ""

    # .env ファイルから環境変数を読み込む (接頭辞なしで直接マッチさせる)
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

# アプリ全体で共有する設定インスタンス
settings = AppSettings()