import os
import glob
import requests
from rich.console import Console
from config import settings

console = Console()

def upload_to_temp_host(filepath: str) -> str:
    """
    ローカル画像を一時ホスティングにアップロードし、公開URLを取得する。
    1つのサービスが落ちていても動作を継続できるよう、複数サービスの自動切り替え（フォールバック）を実装。
    """
    # ブラウザからのアクセスに偽装してボット除け（412エラー等）を回避
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    # --- 候補1: Catbox.moe (最も安定・ボット回避対応) ---
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        with open(filepath, 'rb') as f:
            files = {"fileToUpload": f}
            res = requests.post(url, data=data, files=files, headers=headers, timeout=30)
            res.raise_for_status()
            if res.text.startswith("http"):
                return res.text.strip()
    except Exception as e:
        console.print(f"[yellow]  [警告] 候補1 (Catbox) がダウンしています: {e}[/yellow]")

    # --- 候補2: 0x0.st (エンジニア向けの軽量アップローダー) ---
    try:
        url = "https://0x0.st"
        with open(filepath, 'rb') as f:
            files = {"file": f}
            res = requests.post(url, files=files, headers=headers, timeout=30)
            res.raise_for_status()
            if res.text.startswith("http"):
                return res.text.strip()
    except Exception as e:
        console.print(f"[yellow]  [警告] 候補2 (0x0.st) がダウンしています: {e}[/yellow]")

    # --- 候補3: tmpfiles.org (先日ダウンしていたサーバー) ---
    try:
        url = "https://tmpfiles.org/api/v1/upload"
        with open(filepath, 'rb') as f:
            files = {"file": f}
            res = requests.post(url, files=files, headers=headers, timeout=30)
            res.raise_for_status()
            data = res.json()
            return data["data"]["url"].replace("tmpfiles.org/", "tmpfiles.org/dl/")
    except Exception as e:
        console.print(f"[red]  [エラー] 全ての一時サーバーが利用不可能です。[/red]")
        return ""


def upload_to_printful(output_dir: str):
    """生成された画像をPrintfulへ登録する"""
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
        
        console.print("  -> 一時サーバーで公開URLを発行中...")
        public_url = upload_to_temp_host(img_path)
        
        if not public_url or not public_url.startswith("http"):
            console.print(f"[red]✖ 公開URLの取得に失敗したためスキップします。[/red]")
            continue
            
        console.print(f"  -> URL取得成功: {public_url}")
        
        printful_url = "https://api.printful.com/files"
        payload = {
            "role": "artwork",
            "url": public_url,
            "filename": filename
        }
        
        try:
            console.print("  -> Printfulのライブラリに登録中...")
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
                continue

            res_json = response.json()
            file_id = res_json['result']['id']
            console.print(f"[green]✔ Printful連携成功 (File ID: {file_id})[/green]")
            success_count += 1
            
        except Exception as e:
            console.print(f"[red]✖ 通信エラーが発生しました: {e}[/red]")
                
    console.print(f"[bold green]{success_count}/{len(images)} 件の画像をPrintfulに同期しました！[/bold green]")
    return True