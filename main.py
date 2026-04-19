import os
import json
import base64
import requests
import time
import re
import urllib.parse
from datetime import datetime
import traceback
from PIL import Image, ImageDraw, ImageFont

# --- Configuration (GitHub Secrets) ---
STICKER_LIMIT = int(os.getenv("STICKER_LIMIT", "5"))
OUTPUT_DIR = os.getenv("STICKER_OUTPUT_DIR", "stickers_output")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
PRINTFUL_API_KEY = os.getenv("PRINTFUL_API_KEY", "").strip()
PRINTFUL_STORE_ID = os.getenv("PRINTFUL_STORE_ID", "").strip()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
FREEIMAGE_HOST_KEY = os.getenv("FREEIMAGE_HOST_KEY", "6d207e02198a847aa98d0a2a901485a5").strip()

# Printful Settings
VARIANT_ID = 3559 

def log(msg, error=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = "[ERROR]" if error else "[INFO]"
    print(f"{timestamp} {prefix} {msg}")

def load_endpoints():
    """外部設定ファイルからAPIエンドポイントを読み込み、自動リンクバグをサニタイズする"""
    default_endpoints = {
        "gemini": "generativelanguage.googleapis.com",
        "pollinations": "image.pollinations.ai",
        "freeimage": "freeimage.host",
        "printful": "api.printful.com",
        "hacker_news": "hacker-news.firebaseio.com"
    }
    try:
        with open("endpoints.json", "r") as f:
            raw_data = json.load(f)
            clean_data = {}
            for k, v in raw_data.items():
                match = re.search(r'\]\((.*?)\)', v)
                if match:
                    v = match.group(1)
                v = v.replace("https://", "").replace("http://", "")
                v = v.replace("[", "").replace("]", "").strip()
                clean_data[k] = v
            return clean_data
    except Exception as e:
        log(f"Failed to load endpoints.json: {e}", error=True)
        return default_endpoints

ENDPOINTS = load_endpoints()

# 利用可能なモデルをキャッシュするリスト
AVAILABLE_MODELS_CACHE = []

def get_gemini_model_list():
    """APIから現在のアカウントで利用可能なモデル一覧を自動取得する"""
    global AVAILABLE_MODELS_CACHE
    if AVAILABLE_MODELS_CACHE:
        return AVAILABLE_MODELS_CACHE
        
    base_host = ENDPOINTS.get("gemini")
    url = f"https://{base_host}/v1beta/models?key={GEMINI_API_KEY}"
    
    # 最新モデルを意識したフォールバックリスト
    default_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            models_data = res.json().get("models", [])
            valid_models = [m["name"].split("/")[-1] for m in models_data if "generateContent" in m.get("supportedGenerationMethods", [])]
            
            if valid_models:
                flash_models = [m for m in valid_models if "flash" in m]
                other_models = [m for m in valid_models if "flash" not in m]
                AVAILABLE_MODELS_CACHE = flash_models + other_models
                log(f"APIから利用可能なモデルを自動取得しました: 先頭候補 {AVAILABLE_MODELS_CACHE[0]}")
                return AVAILABLE_MODELS_CACHE
    except Exception as e:
        log(f"モデルの自動取得に失敗しました。デフォルトリストを使用します: {e}")
        
    AVAILABLE_MODELS_CACHE = default_models
    return AVAILABLE_MODELS_CACHE

def call_gemini_text(prompt):
    """Gemini (テキスト生成) - 利用可能なモデルを自動で探してフォールバック"""
    base_host = ENDPOINTS.get("gemini")
    models = get_gemini_model_list()
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    last_error = None
    for model in models:
        url = f"https://{base_host}/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            res = requests.post(url, json=payload, timeout=30)
            res.raise_for_status()
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            last_error = f"{model}: {e}"
            continue 
            
    log(f"Gemini Text API Error (All models failed): {last_error}", error=True)
    return None

def call_gemini_vision_seo(img_path, hn_title):
    """Gemini (画像解析 + SEO生成) - 利用可能なモデルを自動で探してフォールバック"""
    base_host = ENDPOINTS.get("gemini")
    models = get_gemini_model_list()
    
    try:
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
            
        prompt = f"""
        Act as an e-commerce SEO expert. 
        Analyze this sticker image generated from the tech news: "{hn_title}".
        Generate a catchy product title, a 2-sentence description, and 5 relevant tags.
        Return ONLY a JSON object: {{"title": "...", "description": "...", "tags": ["tag1", "tag2"]}}
        """
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": "image/png", "data": img_data}}
                ]
            }]
        }
        
        last_error = None
        for model in models:
            url = f"https://{base_host}/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            try:
                res = requests.post(url, json=payload, timeout=30)
                res.raise_for_status()
                text = res.json()['candidates'][0]['content']['parts'][0]['text']
                match = re.search(r'\{.*\}', text, re.DOTALL)
                return json.loads(match.group()) if match else json.loads(text)
            except Exception as e:
                last_error = f"{model}: {e}"
                continue 
                
        raise Exception(f"All vision models failed. Last error: {last_error}")
        
    except Exception as e:
        log(f"SEO Generation Error: {e}", error=True)
        return {"title": f"Tech Trend Sticker: {hn_title[:20]}", "description": hn_title, "tags": ["tech"]}

def generate_sticker_image(prompt):
    """無料の画像生成APIを使用して画像を生成"""
    try:
        encoded_prompt = urllib.parse.quote(prompt + " sticker design, die-cut, white background, vector art")
        base_host = ENDPOINTS.get("pollinations")
        url = f"https://{base_host}/prompt/{encoded_prompt}?width=512&height=512&nologo=true"
        
        res = requests.get(url, timeout=30)
        if res.status_code == 200:
            return base64.b64encode(res.content).decode('utf-8')
        else:
            log(f"Image API Error: {res.status_code}", error=True)
            return None
    except Exception as e:
        log(f"Image Generation Error: {e}", error=True)
        return None

def generate_fallback_image(text, filepath):
    """外部API障害時: Pillowを使ってローカルでタイポグラフィ画像を生成して突破する"""
    try:
        # ダークグレーの背景画像を作成
        img = Image.new('RGB', (512, 512), color=(40, 44, 52))
        d = ImageDraw.Draw(img)
        
        # タイトルテキストを適当な長さで改行する
        lines = [text[i:i+25] for i in range(0, len(text), 25)]
        y_text = 200
        for line in lines:
            d.text((50, y_text), line, fill=(255, 255, 255))
            y_text += 20
            
        img.save(filepath)
        return True
    except Exception as e:
        log(f"Fallback Image Generation Error: {e}", error=True)
        return False

def upload_to_temp_host(filepath):
    """画像の公開URL化"""
    try:
        base_host = ENDPOINTS.get("freeimage")
        url = f"https://{base_host}/api/1/upload"
        data = {"key": FREEIMAGE_HOST_KEY, "action": "upload", "format": "json"}
        with open(filepath, 'rb') as f:
            res = requests.post(url, data=data, files={"source": f}, timeout=30)
            if res.status_code == 200:
                return res.json()["image"]["url"]
            log(f"Freeimage upload failed: {res.status_code} {res.text}", error=True)
    except Exception as e:
        log(f"Freeimage Host Error: {e}", error=True)
    return ""

def upload_to_printful(public_url, seo_data):
    """Printfulへの出品 (405エラー回避のため事前File追加を廃止し、URL直接指定方式を採用)"""
    headers = {
        "Authorization": f"Bearer {PRINTFUL_API_KEY}",
        "X-PF-Store-Id": PRINTFUL_STORE_ID,
        "Content-Type": "application/json"
    }

    base_host = ENDPOINTS.get("printful")
    
    product_payload = {
        "sync_product": {
            "name": seo_data["title"],
            "thumbnail": public_url
        },
        "sync_variants": [
            {
                "variant_id": VARIANT_ID,
                "retail_price": "7.99",
                "files": [{"url": public_url}]  # 外部URLを直接Printfulにパースさせる
            }
        ]
    }
    
    res = requests.post(f"https://{base_host}/sync/products", headers=headers, json=product_payload, timeout=60)
    return res.json()

def notify_discord(title, public_url, error_msg=None):
    if not DISCORD_WEBHOOK_URL: return
    
    if error_msg:
        content = f"❌ **エラー発生:** {title}\n```{error_msg}```"
    else:
        content = f"🚀 **新商品出品!**\n**Title:** {title}\n**URL:** {public_url}"
        
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    except:
        pass

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    log("Pipeline Started")
    
    base_host = ENDPOINTS.get("hacker_news")
    
    try:
        hn_url = f"https://{base_host}/v0/topstories.json"
        top_ids = requests.get(hn_url).json()
    except Exception as e:
        log(f"Failed to fetch Hacker News: {e}", error=True)
        return
        
    success_count = 0
    
    for story_id in top_ids[:STICKER_LIMIT]:
        try:
            item_url = f"https://{base_host}/v0/item/{story_id}.json"
            story = requests.get(item_url).json()
            hn_title = story.get('title')
            log(f"Processing: {hn_title}")

            log("Generating Text Prompt...")
            sys_prompt = f"Create a professional sticker design prompt for: '{hn_title}'. Output ONLY the visual prompt in English."
            image_prompt = call_gemini_text(sys_prompt)
            if not image_prompt: 
                log("Failed to generate prompt", error=True)
                continue
            
            log("Generating Image...")
            img_b64 = generate_sticker_image(image_prompt)
            filepath = os.path.join(OUTPUT_DIR, f"{story_id}.png")
            
            # APIが成功すれば画像を保存、失敗すればローカルで代替生成する
            if img_b64: 
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(img_b64))
            else:
                log("Image API Failed. Using local fallback generation...")
                if not generate_fallback_image(hn_title, filepath):
                    log("All image generation methods failed.", error=True)
                    continue

            log("Generating SEO Data...")
            seo_data = call_gemini_vision_seo(filepath, hn_title)

            log("Uploading to Freeimage.host...")
            public_url = upload_to_temp_host(filepath)
            if not public_url: 
                log("Failed to upload image to host", error=True)
                continue

            log("Uploading to Printful...")
            result = upload_to_printful(public_url, seo_data)
            
            if 'error' in str(result).lower():
                log(f"Printful Upload Failed: {result}", error=True)
                notify_discord(hn_title, None, str(result))
            else:
                log(f"Success: {seo_data['title']}")
                notify_discord(seo_data['title'], public_url)
                success_count += 1
                
        except Exception as e:
            log(f"Error processing story {story_id}: {traceback.format_exc()}", error=True)
            
        time.sleep(5)

    log(f"Pipeline Completed. Success: {success_count}/{STICKER_LIMIT}")

if __name__ == "__main__":
    main()
