import typer
from rich.console import Console
from rich.panel import Panel
import os

# 自作モジュールのインポート
from config import settings
from trend_scorer_cli import run_scraper
# generate_stickers.py から画像生成関数だけをインポート
from generate_stickers import generate_images
import pandas as pd

app = typer.Typer(help="トレンド取得からステッカー生成までの自動パイプライン")
console = Console()

@app.command()
def run_pipeline(
    limit: int = typer.Option(settings.limit, help="処理する件数"),
    csv_file: str = typer.Option(settings.input_file, help="中間データのCSVファイル名"),
    output_dir: str = typer.Option(settings.output_dir, help="画像出力先フォルダ")
):
    console.rule("[bold blue]🚀 Sticker Automation Pipeline Start[/bold blue]")
    
    # --- Step 1: データ取得 ---
    console.print(Panel("[bold yellow]Step 1: トレンドデータの取得[/bold yellow]", border_style="yellow"))
    success = run_scraper(limit=limit, output_file=csv_file)
    if not success:
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
        
    console.rule("[bold green]✨ All Processes Completed Successfully![/bold green]")

if __name__ == "__main__":
    app()