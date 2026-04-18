import os
import typer
import pandas as pd
from rich.console import Console
from rich.panel import Panel

# 各モジュールからの機能インポート
from config import settings
from trend_scorer_cli import run_scraper
from generate_stickers import generate_images
from printful_exporter import upload_to_printful
from feedback_manager import apply_negative_feedback

app = typer.Typer()
console = Console()

@app.command()
def main():
    # 設定値の安全な読み込み（config.py に無い場合はデフォルト値や環境変数を使う）
    csv_file = getattr(settings, 'input_file', 'hn_trends_analyzed.csv')
    output_dir = getattr(settings, 'output_dir', 'stickers_output')
    limit = int(getattr(settings, 'sticker_limit', os.getenv('STICKER_LIMIT', 5)))

    console.rule("[bold blue]Sticker Automation Pipeline[/bold blue]")

    # --- Step 1: トレンドデータの取得と採点 ---
    console.print(Panel("[bold yellow]Step 1: トレンドデータの取得と採点[/bold yellow]", border_style="yellow"))
    try:
        success = run_scraper(limit=limit, output_file=csv_file)
        if not success:
            raise Exception("データ取得に失敗しました。")
    except Exception as e:
        console.print(f"[bold red]スクレイピング中にエラーが発生しました: {e}[/bold red]")
        raise typer.Exit(code=1)
        
    console.print("\n")

    # --- Step 1.5: ネガティブ・フィードバックの適用 ---
    console.print(Panel("[bold yellow]Step 1.5: 機械学習フィードバック（負のデータの適用）[/bold yellow]", border_style="yellow"))
    try:
        df = pd.read_csv(csv_file)
        df = apply_negative_feedback(df)
        df.to_csv(csv_file, index=False)
    except Exception as e:
        console.print(f"[bold red]フィードバック適用中にエラーが発生しました: {e}[/bold red]")
        raise typer.Exit(code=1)
    
    console.print("\n")

    # --- Step 2: 画像生成 ---
    console.print(Panel("[bold yellow]Step 2: ステッカー画像の生成[/bold yellow]", border_style="yellow"))
    try:
        df = pd.read_csv(csv_file)
        generate_images(df, output_dir=output_dir)
    except Exception as e:
        console.print(f"[bold red]画像生成中にエラーが発生しました: {e}[/bold red]")
        raise typer.Exit(code=1)
        
    console.print("\n")
    
    # --- Step 3: Printful API連携 ---
    console.print(Panel("[bold yellow]Step 3: Printfulへの自動アップロード[/bold yellow]", border_style="yellow"))
    try:
        upload_to_printful(output_dir=output_dir)
    except Exception as e:
        console.print(f"[bold red]Printful連携中にエラーが発生しました: {e}[/bold red]")
        raise typer.Exit(code=1)

    console.rule("[bold green]✨ All Processes Completed Successfully![/bold green]")

if __name__ == "__main__":
    app()