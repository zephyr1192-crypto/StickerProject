import os
import glob
import requests
from rich.console import Console
from config import settings

console = Console()

def upload_to_printful(output_dir: str):
    """生成されたステッカー画像をPrintfulのファイルライブラリにアップロードする"""
    api_key = settings.printful_api_key
    if not api_key or api_key == "your_printful_api_key_here":
        console.print("[yellow]Printful APIキーが設定されていないため、自動アップロードをスキップします。[/yellow]")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    # 最新版（v2）のPNG画像を対象とする
    images = glob.glob(os.path.join(output_dir, "premium_v2_*.png"))
    if not images:
        console.print("[yellow]アップロードする画像が見つかりません。[/yellow]")
        return False

    success_count = 0
    for img_path in images:
        filename = os.path.basename(img_path)
        console.print(f"[cyan]Printfulへ送信中: {filename}[/cyan]")
        
        url = "https://api.printful.com/files"
        
        try:
            with open(img_path, 'rb') as f:
                # Printful APIが要求するmultipart/form-data形式で送信
                files = {'file': (filename, f, 'image/png')}
                response = requests.post(url, headers=headers, files=files)
            
            response.raise_for_status()
            data = response.json()
            file_id = data['result']['id']
            console.print(f"[green]✔ アップロード完了 (File ID: {file_id})[/green]")
            success_count += 1
            
        except requests.exceptions.RequestException as e:
            console.print(f"[red]✖ アップロード失敗 ({filename}): {e}[/red]")
            if e.response is not None:
                console.print(f"[red]詳細: {e.response.text}[/red]")
                
    console.print(f"[bold green]{success_count}/{len(images)} 件の画像をPrintfulライブラリに同期しました。[/bold green]")
    return True