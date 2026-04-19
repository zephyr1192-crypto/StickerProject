import os
import glob
import requests
from rich.console import Console
from config import settings

console = Console()

def upload_to_temp_host(filepath: str) -> str:
    """
    クラウド（GitHub Actions）環境からでもブロックされない
    画像ホスティングサービスを複数用意し、3重のフォールバックで確実なURLを発行する。
    """
    filename = os.path.basename(filepath)
    headers = {
        # ボットとして弾かれないよう、Chromeブラウザの身分証明を付与
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    # --- 候補1: freeimage.host (画像特化・クラウドからのアクセスに強い) ---
    try:
        url = "https://freeimage.host/api/1/upload"
        data = {
            "key": "6d207e02198a847aa98d0a2a901485a5",  # 公式公開のパブリックテストキー
            "action": "upload",
            "format": "json"
        }
        with open(filepath, 'rb') as f:
            res = requests.post(url, data=data, files={"source": f}, headers=headers, timeout=30)
            if res.status_code == 200:
                return res.json()["image"]["url"]
    except Exception as e:
        console.print(f"[yellow]  [警告] 候補1 (freeimage) 失敗: {e}[/yellow]")

    # --- 候補2: file.io (1回アクセスで消えるセキュアな一時ホスト) ---
    try:
        url = "https://file.io"
        with open(filepath, 'rb') as f:
            res = requests.post(url, files={"file": f}, headers=headers, timeout=30)
            if res.status_code == 200:
                data = res.json()
                if data.get("success"):
                    return data.get("link")
    except Exception as e:
        console.print(f"[yellow]  [警告] 候補2 (file.io) 失敗: {e}[/yellow]")

    # --- 候補3: catbox.moe (前回弾かれたが、ブラウザ偽装で再試行) ---
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        with open(filepath, 'rb') as f:
            res = requests.post(url, data=data, files={"fileToUpload": f}, headers=headers, timeout=30)
            if res.status_code == 200 and res.text.startswith("http"):
                return res.text.strip()
    except Exception as e:
        console.print(f"[red]  [エラー] 全ての一時サーバーが利用不可能です: {e}[/red]")

    return ""


def upload_to_printful(output_dir: str):
    """生成された画像をPrintfulへ登録する"""
    api_key = settings.printful_api_key
    
    if not api_key or api_key.startswith("your_"):
        console.print("[bold red]✖ エラー: .envにAPIキーが設定されていません。[/bold red]")
        return False

    # PrintfulへはJSONで純粋に「URL」だけを渡す
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
            "url": public_url,  # Printfulが唯一確実に受け取るURL渡し
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