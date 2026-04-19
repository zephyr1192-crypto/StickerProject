import os
import glob
import json
import re
import requests
import pandas as pd
import google.generativeai as genai
import PIL.Image
from rich.console import Console
from config import settings

console = Console()

def generate_seo_metadata(img_path: str, hn_title: str, context_tag: str) -> dict:
    """Gemini (無料枠) を用いて、画像と元タイトルからSEOテキストを生成する"""
    if not settings.gemini_api_key:
        console.print("[yellow]Gemini APIキーが未設定のため、AIによるSEO生成をスキップします。[/yellow]")
        return {"title": f"Sticker: {hn_title[:40]}", "description": hn_title, "tags": [context_tag]}

    try:
        genai.configure(api_key=settings.gemini_api_key)
        # モデル名の指定をより標準的な形式に変更
        model = genai.GenerativeModel('gemini-1.5-flash')
        img = PIL.Image.open(img_path)
        
        prompt = f"""
        あなたはプロのECマーケターです。以下のHacker Newsのタイトルと、生成されたステッカー画像に基づいて、ECサイトで売れる英語の商品情報を生成してください。
        
        元タイトル: {hn_title}
        カテゴリタグ: {context_tag}
        
        出力は以下のJSONフォーマットのみを返してください。
        {{
            "title": "SEOに強い商品名 (英語、50文字以内)",
            "description": "魅力的な商品説明文 (英語、300文字以内)",
            "tags": ["tag1", "tag2", "tag3"]
        }}
        """
        response = model.generate_content([prompt, img])
        text = response.text
        
        # JSON抽出のロジックを強化
        match = re.search(r'\{.*\}', text, re.DOTALL)
        json_str = match.group() if match else text
        return json.loads(json_str)
    except Exception as e:
        console.print(f"[red]Gemini APIエラー (スキップして続行します): {e}[/red]")
        # 失敗しても止まらないようにデフォルト値を返す
        return {"title": f"Sticker: {hn_title[:40]}", "description": hn_title, "tags": ["tech"]}

def upload_to_temp_host(filepath: str) -> str:
    """一時ホストへのアップロード。失敗した場合は理由を表示する"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # 候補1: freeimage.host
    try:
        url = "https://freeimage.host/api/1/upload"
        data = {"key": "6d207e02198a847aa98d0a2a901485a5", "action": "upload", "format": "json"}
        with open(filepath, 'rb') as f:
            res = requests.post(url, data=data, files={"source": f}, headers=headers, timeout=30)
            if res.status_code == 200:
                return res.json()["image"]["url"]
    except Exception as e:
        console.print(f"  [dim]一時ホスト1失敗: {e}[/dim]")

    # 候補2: file.io
    try:
        url = "https://file.io"
        with open(filepath, 'rb') as f:
            res = requests.post(url, files={"file": f}, headers=headers, timeout=30)
            if res.status_code == 200 and res.json().get("success"):
                return res.json().get("link")
    except Exception as e:
        console.print(f"  [dim]一時ホスト2失敗: {e}[/dim]")
    
    return ""

def upload_to_printful(output_dir: str, df: pd.DataFrame):
    """Printfulへの登録と出品。エラー詳細を表示するように改良"""
    api_key = settings.printful_api_key
    store_id = settings.printful_store_id
    
    if not api_key:
        console.print("[bold red]✖ Printful APIキーが設定されていません。[/bold red]")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if store_id:
        headers["X-PF-Store-Id"] = str(store_id)

    images = sorted(glob.glob(os.path.join(output_dir, "premium_v2_*.png")))
    success_count = 0

    for idx, img_path in enumerate(images):
        filename = os.path.basename(img_path)
        console.print(f"[cyan]処理中 ({idx+1}/{len(images)}): {filename}[/cyan]")
        
        hn_title = df.iloc[idx]['title'] if idx < len(df) else "Awesome Sticker"
        context_tag = df.iloc[idx]['context_tag'] if idx < len(df) else "Tech"
        
        # 1. Gemini SEO
        seo_data = generate_seo_metadata(img_path, hn_title, context_tag)

        # 2. Upload to Temp Host
        public_url = upload_to_temp_host(img_path)
        if not public_url:
            console.print("  [red]✖ 公開URLの取得に失敗しました。[/red]")
            continue

        # 3. Printful File Library
        console.print("  -> Printfulライブラリに送信中...")
        file_payload = {"role": "artwork", "url": public_url, "filename": filename}
        file_res = requests.post("https://api.printful.com/files", headers=headers, json=file_payload, timeout=60)
        
        if file_res.status_code != 200:
            console.print(f"  [red]✖ ライブラリ登録エラー: {file_res.status_code} - {file_res.text}[/red]")
            continue
        
        file_id = file_res.json()['result']['id']
        
        # 4. Printful Product Creation
        if store_id:
            console.print(f"  -> ストア(ID:{store_id})へ出品中...")
            product_payload = {
                "sync_product": {
                    "name": seo_data["title"],
                    "thumbnail": public_url
                },
                "sync_variants": [
                    {
                        "variant_id": 3559, # Kiss-cut sticker
                        "retail_price": "5.99",
                        "files": [{"id": file_id}]
                    }
                ]
            }
            prod_res = requests.post("https://api.printful.com/store/products", headers=headers, json=product_payload, timeout=60)
            
            if prod_res.status_code in [200, 201]:
                console.print("[green]  ✔ 出品完了！[/green]")
                success_count += 1
            else:
                console.print(f"  [yellow]⚠ 出品失敗 (理由: {prod_res.text})[/yellow]")
        else:
            success_count += 1

    console.print(f"\n[bold green]最終結果: {success_count}/{len(images)} 件の処理を完了しました。[/bold green]")
    return True