import typer
import pandas as pd
import os
import requests
from rich.console import Console
from rich.panel import Panel

from config import settings
from trend_scorer_cli import run_scraper 
from generate_stickers import generate_images
from printful_exporter import upload_to_printful

app = typer.Typer()
console = Console()

def send_discord_notification(success=True, message=""):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url: return

    content = "✅ **ステッカー自動生成＆自動出品完了！**\nGeminiによるSEO解析とPrintfulストアへの出品が終わりました。\nギャラリー: https://zephyr1192-crypto.github.io/StickerProject/" if success else f"🚨 **【警告】ステッカー生成でエラーが発生しました！**\n詳細: {message}"
    try:
        requests.post(webhook_url, json={"content": content}, timeout=10)
    except Exception:
        pass

@app.command()
def main():
    csv_file = settings.input_file
    output_dir = settings.output_dir
    limit = int(settings.sticker_limit)

    console.rule("[bold blue]Sticker Automation Pipeline with Gemini AI[/bold blue]")

    try:
        console.print(Panel("[bold yellow]Step 1: Hacker Newsトレンド取得[/bold yellow]", border_style="yellow"))
        if not run_scraper(limit=limit, output_file=csv_file):
            raise Exception("データ取得失敗")

        console.print(Panel("[bold yellow]Step 2: ステッカー生成[/bold yellow]", border_style="yellow"))
        df = pd.read_csv(csv_file)
        generate_images(df, output_dir=output_dir)

        console.print(Panel("[bold yellow]Step 3: Gemini SEO解析 ＆ Printful自動出品[/bold yellow]", border_style="yellow"))
        # Pandasのデータフレーム(df)を渡して、AIが元の記事タイトルを読み取れるように変更
        upload_to_printful(output_dir=output_dir, df=df)

        console.rule("[bold green]✨ 全工程完了！[/bold green]")
        send_discord_notification(success=True)

    except Exception as e:
        console.print(f"[bold red]エラー: {e}[/bold red]")
        send_discord_notification(success=False, message=str(e))
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()