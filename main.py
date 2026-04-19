import typer
import pandas as pd
import os
import requests
from rich.console import Console
from rich.panel import Panel

# 各モジュールからの機能インポート
from config import settings
from hn_trend_scorer import fetch_top_story_ids, fetch_story_details, process_and_analyze
from generate_stickers import generate_images
from printful_exporter import upload_to_printful

app = typer.Typer()
console = Console()

def send_discord_notification(success=True, message=""):
    """Discordに処理結果を通知する"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        console.print("[yellow]Discord Webhook URLが設定されていないため、通知をスキップします。[/yellow]")
        return

    content = "✅ **ステッカー自動生成完了！**\nPrintfulへの納品とギャラリーの更新が終わりました。\nギャラリーを確認: https://zephyr1192-crypto.github.io/StickerProject/" if success else f"🚨 **【警告】ステッカー生成でエラーが発生しました！**\n詳細: {message}"
    
    try:
        requests.post(webhook_url, json={"content": content}, timeout=10)
        console.print("[green]Discordへ通知を送信しました。[/green]")
    except Exception as e:
        console.print(f"[red]Discord通知の送信に失敗しました: {e}[/red]")

@app.command()
def main():
    # 設定の読み込み
    csv_file = settings.input_file
    output_dir = settings.output_dir
    limit = int(settings.sticker_limit)

    console.rule("[bold blue]Sticker Automation Pipeline[/bold blue]")

    try:
        # --- Step 1: データ取得 ---
        console.print(Panel("[bold yellow]Step 1: Hacker Newsトレンド取得[/bold yellow]", border_style="yellow"))
        ids = fetch_top_story_ids(limit=limit * 2)
        details = fetch_story_details(ids)
        df = process_and_analyze(details)
        df.to_csv(csv_file, index=False)
        console.print(f"[green]データを {csv_file} に保存しました。[/green]")

        # --- Step 2: 画像生成 ---
        console.print(Panel("[bold yellow]Step 2: ステッカー生成[/bold yellow]", border_style="yellow"))
        df = pd.read_csv(csv_file)
        generate_images(df, output_dir=output_dir)

        # --- Step 3: Printfulアップロード ---
        console.print(Panel("[bold yellow]Step 3: Printful同期[/bold yellow]", border_style="yellow"))
        upload_to_printful(output_dir=output_dir)

        console.rule("[bold green]✨ 全工程完了！[/bold green]")
        
        # 成功通知
        send_discord_notification(success=True)

    except Exception as e:
        console.print(f"[bold red]エラーが発生しました: {e}[/bold red]")
        # 失敗通知
        send_discord_notification(success=False, message=str(e))
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()