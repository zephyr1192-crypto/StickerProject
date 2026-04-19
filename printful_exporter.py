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
    """Gemini 1.5 Flash (無料枠) を用いて、画像と元タイトルからSEOテキストを生成する"""
    if not settings.gemini_api_key:
        console.print("[yellow]Gemini APIキーが未設定のため、AIによるSEO生成をスキップします。[/yellow]")
        return {"title": f"Hacker News Sticker: {hn_title[:40]}", "description": hn_title, "tags": [context_tag]}

    try:
        genai.configure(api_key=settings.gemini_api_key)
        # 無料枠で最も高速なマルチモーダルモデルを使用
        model = genai.GenerativeModel('gemini-1.5-flash')
        img = PIL.Image.open(img_path)
        
        prompt = f"""
        あなたはプロのECマーケターです。以下のHacker Newsのタイトルと、生成されたステッカー画像に基づいて、Shopify/Etsy等のECサイトで売れるステッカー商品の情報を英語で生成してください。
        
        元タイトル: {hn_title}
        カテゴリタグ: {context_tag}
        
        出力は以下のJSONフォーマットのみを厳密に返してください。Markdown記法は絶対に含めないでください。
        {{
            "title": "SEOに強い商品名 (英語、50文字以内)",
            "description": "購買意欲をそそる魅力的な商品説明文 (英語、300文字以内)",
            "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
        }}
        """
        response = model.generate_content([prompt, img])
        text = response.text
        
        # JSON部分の安全な抽出
        match = re.search(r'\{.*\}', text, re.DOTALL)
        json_str = match.group() if match else text
        
        metadata = json.loads(json_str)
        return metadata
    except Exception as e:
        console.print(f"[red]Gemini APIの処理中にエラーが発生しました: {e}[/red]")
        return {"title": f"Sticker: {hn_title[:40]}", "description": hn_title, "tags": ["tech"]}

def upload_to_temp_host(filepath: str) -> str:
    """一時ホストへのアップロード処理"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0"}
    try:
        url = "https://freeimage.host/api/1/upload"
        data = {"key": "6d207e02198a847aa98d0a2a901485a5", "action": "upload", "format": "json"}
        with open(filepath, 'rb') as f:
            res = requests.post(url, data=data, files={"source": f}, headers=headers, timeout=30)
            if res.status_code == 200:
                return res.json()["image"]["url"]
    except Exception:
        pass
    try:
        url = "https://file.io"
        with open(filepath, 'rb') as f:
            res = requests.post(url, files={"file": f}, headers=headers, timeout=30)
            if res.status_code == 200 and res.json().get("success"):
                return res.json().get("link")
    except Exception:
        pass
    return ""

def upload_to_printful(output_dir: str, df: pd.DataFrame):
    """GeminiでSEO情報を付与し、Printfulストアに商品(Sync Product)として自動出品する"""
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
        console.print(f"[cyan]処理中: {filename}[/cyan]")
        
        # DataFrameから元の記事情報を取得
        hn_title = df.iloc[idx]['title'] if idx < len(df) else "Awesome Sticker"
        context_tag = df.iloc[idx]['context_tag'] if idx < len(df) else "Tech"
        
        # 1. GeminiでSEO文を生成
        console.print("  -> Gemini APIでSEO商品情報を生成中...")
        seo_data = generate_seo_metadata(img_path, hn_title, context_tag)
        console.print(f"  -> 生成されたタイトル: [bold]{seo_data['title']}[/bold]")

        # 2. 一時ホストへアップロード
        console.print("  -> 一時サーバーで公開URLを発行中...")
        public_url = upload_to_temp_host(img_path)
        if not public_url: continue

        # 3. PrintfulのFile Libraryへ登録
        console.print("  -> Printfulのライブラリに登録中...")
        file_res = requests.post("https://api.printful.com/files", headers=headers, json={"role": "artwork", "url": public_url, "filename": filename}, timeout=60)
        if file_res.status_code != 200: continue
        file_id = file_res.json()['result']['id']
        
        # 4. ストアへ新商品として自動出品
        if store_id:
            console.print("  -> ストアへ新商品として自動出品中...")
            # Kiss-Cut Stickers (5.5x5.5) の一般的なバリアントID=3559を使用
            product_payload = {
                "sync_product": {
                    "name": seo_data["title"],
                    "thumbnail": public_url
                },
                "sync_variants": [
                    {
                        "variant_id": 3559, 
                        "retail_price": "5.99",
                        "files": [{"id": file_id}]
                    }
                ]
            }
            prod_res = requests.post("https://api.printful.com/store/products", headers=headers, json=product_payload, timeout=60)
            if prod_res.status_code in [200, 201]:
                console.print("[green]✔ ストアへの自動出品が完了しました！[/green]")
                success_count += 1
            else:
                console.print(f"[yellow]⚠ 出品エラー (ライブラリには保存済): {prod_res.text}[/yellow]")
        else:
            success_count += 1

    console.print(f"[bold green]{success_count}/{len(images)} 件の処理を完了しました！[/bold green]")
    return True