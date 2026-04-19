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
    """Gemini 1.5 Flash を用いてSEOテキストを生成。モデル名の不一致を解消。"""
    if not settings.gemini_api_key:
        return {"title": f"Sticker: {hn_title[:40]}", "description": hn_title, "tags": [context_tag]}

    try:
        genai.configure(api_key=settings.gemini_api_key)
        # モデル名を 'gemini-1.5-flash' に固定
        model = genai.GenerativeModel('gemini-1.5-flash')
        img = PIL.Image.open(img_path)
        
        prompt = f"""
        Act as an e-commerce SEO expert. Generate a product title and description for this sticker image.
        Source Title: {hn_title}
        Category: {context_tag}
        Return ONLY a JSON object: {{"title": "...", "description": "...", "tags": ["..."]}}
        """
        response = model.generate_content([prompt, img])
        
        # JSON抽出
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        return json.loads(match.group()) if match else json.loads(response.text)
    except Exception as e:
        console.print(f"[red]Gemini APIエラー (デフォルトを使用): {e}[/red]")
        return {"title": f"Sticker: {hn_title[:40]}", "description": hn_title, "tags": ["tech"]}

def upload_to_temp_host(filepath: str) -> str:
    """画像を一時的に公開URL化する"""
    try:
        url = "https://freeimage.host/api/1/upload"
        data = {"key": "6d207e02198a847aa98d0a2a901485a5", "action": "upload", "format": "json"}
        with open(filepath, 'rb') as f:
            res = requests.post(url, data=data, files={"source": f}, timeout=30)
            if res.status_code == 200:
                return res.json()["image"]["url"]
    except:
        pass
    return ""

def upload_to_printful(output_dir: str, df: pd.DataFrame):
    """Printfulへの登録と出品。Store IDの状態を可視化。"""
    api_key = str(settings.printful_api_key).strip()
    store_id = str(settings.printful_store_id).strip()
    
    # Store IDの状態をログに出力（デバッグ用）
    if not store_id:
        console.print("[bold yellow]⚠ PRINTFUL_STORE_ID が空です。ライブラリ保存のみ実行します。[/bold yellow]")
    else:
        console.print(f"[green]✔ Store IDを検知しました: {store_id}[/green]")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if store_id:
        headers["X-PF-Store-Id"] = store_id

    images = sorted(glob.glob(os.path.join(output_dir, "premium_v2_*.png")))
    success_count = 0

    for idx, img_path in enumerate(images):
        filename = os.path.basename(img_path)
        console.print(f"[cyan]開始中 ({idx+1}/{len(images)}): {filename}[/cyan]")
        
        hn_title = df.iloc[idx]['title'] if idx < len(df) else "Awesome Sticker"
        context_tag = df.iloc[idx]['context_tag'] if idx < len(df) else "Tech"
        
        seo_data = generate_seo_metadata(img_path, hn_title, context_tag)
        public_url = upload_to_temp_host(img_path)
        
        if not public_url:
            console.print("  [red]✖ 画像のURL化に失敗しました。[/red]")
            continue

        # 1. Printfulライブラリに保存
        file_payload = {"role": "artwork", "url": public_url, "filename": filename}
        file_res = requests.post("https://api.printful.com/files", headers=headers, json=file_payload, timeout=60)
        
        if file_res.status_code != 200:
            console.print(f"  [red]✖ 認証/登録エラー: {file_res.status_code} - {file_res.text}[/red]")
            continue
        
        file_id = file_res.json()['result']['id']
        
        # 2. ストアに出品（Store IDがある場合のみ）
        if store_id:
            product_payload = {
                "sync_product": {"name": seo_data["title"], "thumbnail": public_url},
                "sync_variants": [{"variant_id": 3559, "retail_price": "5.99", "files": [{"id": file_id}]}]
            }
            prod_res = requests.post("https://api.printful.com/store/products", headers=headers, json=product_payload, timeout=60)
            
            if prod_res.status_code in [200, 201]:
                console.print(f"  [bold green]✔ 出品成功！ストアに商品が追加されました。[/bold green]")
                success_count += 1
            else:
                console.print(f"  [red]✖ 出品失敗: {prod_res.text}[/red]")
        else:
            success_count += 1

    console.print(f"\n[bold green]最終結果: {success_count}/{len(images)} 件の処理を完了。[/bold green]")
    return True