import os
import glob
import base64
import requests
from rich.console import Console
from config import settings

console = Console()

def upload_to_printful(output_dir: str):
    """
    生成された画像をPrintfulへ登録する。
    不安定な一時サーバーを廃止し、Printful公式仕様である 
    `base64` パラメータを用いた直接アップロード方式を採用。
    """
    api_key = settings.printful_api_key
    
    if not api_key or api_key.startswith("your_"):
        console.print("[bold red]✖ エラー: .envにAPIキーが設定されていません。[/bold red]")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    images = glob.glob(os.path.join(output_dir, "premium_v2_*.png"))
    if not images:
        console.print("[yellow]アップロード対象の画像が見つかりません。[/yellow]")
        return False

    success_count = 0
    for img_path in images:
        filename = os.path.basename(img_path)
        console.print(f"[cyan]処理中: {filename}[/cyan]")
        
        try:
            # 画像ファイルを読み込み、純粋なBase64文字列に変換
            with open(img_path, "rb") as f:
                img_data = f.read()
                base64_data = base64.b64encode(img_data).decode("utf-8")
                
            printful_url = "https://api.printful.com/files"
            
            # Printful公式仕様に完全準拠した直接送信ペイロード
            payload = {
                "role": "artwork",
                "base64": base64_data,  # urlではなくbase64パラメータを使用
                "filename": filename
            }
            
            console.print("  -> Printfulのライブラリに直接登録中...")
            response = requests.post(
                printful_url, 
                headers=headers, 
                json=payload,
                timeout=60
            )
            
            if response.status_code == 401:
                console.print("[bold red]✖ 認証エラー (401): APIキーが無効です。[/bold red]")
                return False
                
            if response.status_code != 200:
                console.print(f"[red]✖ Printfulへの登録失敗: {response.status_code}[/red]")
                console.print(f"[red]詳細: {response.text}[/red]")
                continue

            res_json = response.json()
            file_id = res_json['result']['id']
            console.print(f"[green]✔ Printful連携成功 (File ID: {file_id})[/green]")
            success_count += 1
            
        except Exception as e:
            console.print(f"[red]✖ 通信エラーが発生しました: {e}[/red]")
                
    console.print(f"[bold green]{success_count}/{len(images)} 件の画像をPrintfulに同期しました！[/bold green]")
    return True