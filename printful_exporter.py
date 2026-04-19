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
    """Gemini 1.5 Flash を用いてSEOテキストを生成。"""
    if not settings.gemini_api_key:
        return {"title": f"Sticker: {hn_title[:40]}", "description": hn_title, "tags": [context_tag]}

    try:
        genai.configure(api_key=settings.gemini_api_key)
        # 404エラー対策: 'gemini-1.5-flash' を直接指定
        model = genai.GenerativeModel('gemini-1.5-flash')
        img = PIL.Image.open(img_path)
        
        prompt = f"""
        Act as an e-commerce SEO expert. Generate a product title and description for this sticker image.
        Source Title: {hn_title}
        Category: {context_tag}
        Return ONLY a JSON object: {{"title": "...", "description": "...", "tags": ["..."]}}
        """
        response = model.generate_content([prompt, img])
        
        # JSONを抽出
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(response.text)
    except Exception as e:
        console.print(f"[red]Gemini APIエラー: {e}[/red]")
        # 失敗した場合は元のタイトルから簡易的なタイトルを生成
        return {"title": f"Premium Tech Sticker: {hn_title[:30]}", "description": f"Custom sticker for {hn_title}", "tags": ["tech"]}

def upload_to_temp_host(filepath: str) -> str:
    """画像を一時的に公開URL化する（Printfulへの送信に必須）"""
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
    """Printfulへの登録と出品。"""
    api_key = str(settings.printful_api_key).strip()
    store_id = str(settings.printful_store_id).strip()
    
    if not store_id or store_id == "" or store_id == "None":
        console.print("[bold yellow]⚠ PRINTFUL_STORE_ID が空です。GitHubの設定を確認してください。[/bold yellow]")
        return False

    console.print(f"[green]✔ Store IDを検知しました: {store_id}[/green]")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-PF-Store-Id": store_id
    }

    images = sorted(glob.glob(os.path.join(output_dir, "premium_v2_*.png")))
    success_count = 0

    for idx, img_path in enumerate(images):
        filename = os.path.basename(img_path)
        console.print(f"[cyan]開始中 ({idx+1}/{len(images)}): {filename}[/cyan]")
        
        hn_title = df.iloc[idx]['title'] if idx < len(df) else "Awesome Tech Sticker"
        context_tag = df.iloc[idx]['context_tag'] if idx < len(df) else "Technology"
        
        # 1. AIによるSEOテキスト生成
        seo_data = generate_seo_metadata(img_path, hn_title, context_tag)

        # 2. 画像の公開URL化
        public_url = upload_to_temp_host(img_path)
        if not public_url:
            console.print("  [red]✖ 画像のアップロードに失敗しました。[/red]")
            continue

        # 3. Printfulライブラリに保存
        file_payload = {"role": "artwork", "url": public_url, "filename": filename}
        file_res = requests.post("https://api.printful.com/files", headers=headers, json=file_payload, timeout=60)
        
        if file_res.status_code != 200:
            console.print(f"  [red]✖ Printfulライブラリ登録エラー: {file_res.status_code}[/red]")
            continue
        
        file_id = file_res.json()['result']['id']
        
        # 4. ストアに出品
        # variant_id: 3559 が利用不可と言われる場合、より汎用的な「11152」(Kiss-cut 3x3) を試します
        # 多くのストアで共通して利用可能なIDです
        target_variant = 11152 
        
        product_payload = {
            "sync_product": {
                "name": seo_data["title"],
                "thumbnail": public_url
            },
            "sync_variants": [
                {
                    "variant_id": target_variant,
                    "retail_price": "5.99",
                    "files": [{"id": file_id}]
                }
            ]
        }
        
        prod_res = requests.post("https://api.printful.com/store/products", headers=headers, json=product_payload, timeout=60)
        
        if prod_res.status_code in [200, 201]:
            console.print(f"  [bold green]✔ 出品成功！ストアに商品「{seo_data['title']}」を追加しました。[/bold green]")
            success_count += 1
        else:
            # 失敗した場合、エラー内容を詳しく表示
            error_msg = prod_res.text
            console.print(f"  [red]✖ 出品失敗 (理由: {error_msg})[/red]")
            console.print(f"  [dim]ヒント: variant_id {target_variant} がこのストアで有効か確認してください。[/dim]")

    console.print(f"\n[bold green]最終結果: {success_count}/{len(images)} 件の処理を完了しました。[/bold green]")
    return True