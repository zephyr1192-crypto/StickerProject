import os
import json
import base64
import requests
import time
import re
from datetime import datetime
import traceback

# --- Configuration (GitHub Secrets) ---
STICKER_LIMIT = int(os.getenv("STICKER_LIMIT", "5"))
OUTPUT_DIR = os.getenv("STICKER_OUTPUT_DIR", "stickers_output")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
PRINTFUL_API_KEY = os.getenv("PRINTFUL_API_KEY", "").strip()
PRINTFUL_STORE_ID = os.getenv("PRINTFUL_STORE_ID", "").strip()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
FREEIMAGE_HOST_KEY = os.getenv("FREEIMAGE_HOST_KEY", "6d207e02198a847aa98d0a2a901485a5").strip()

# Models
TEXT_VISION_MODEL = "gemini-2.5-flash-preview-09-2025"
IMAGE_MODEL = "imagen-4.0-generate-001"

# Printful Settings
# 11152で400エラーが出たため、Kiss-cut Stickers (3"x3") の標準的なID 3559 に変更
VARIANT_ID = 3559 

def log(msg, error=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = "[ERROR]" if error else "[INFO]"
    print(f"{timestamp} {prefix} {msg}")

def call_gemini_text(prompt):
    """テキスト生成"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_VISION_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    for i in range(5):
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            if i == 4:
                log(f"Gemini Text API Error: {e}", error=True)
                return None
            time.sleep(2**i)
    return None

def call_gemini_vision_seo(img_path, hn_title):
    """画像解析によるSEO生成"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_VISION_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
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
        
        for i in range(5):
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                text = response.json()['candidates'][0]['content']['parts'][0]['text']
                match = re.search(r'\{.*\}', text, re.DOTALL)
                return json.loads(match.group()) if match else json.loads(text)
            time.sleep(2**i)
            
        raise Exception("API Retry limit exceeded")
    except Exception as e:
        log(f"SEO Generation Error: {e}", error=True)
        return {"title": f"Tech Trend Sticker: {hn_title[:20]}", "description": hn_title, "tags": ["tech"]}

def generate_sticker_image(prompt):
    """画像生成"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGE_MODEL}:predict?key={GEMINI_API_KEY}"
    payload = {
        "instances": {"prompt": prompt},
        "parameters": {"sampleCount": 1}
    }
    
    for i in range(5):
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()['predictions'][0]['bytesBase64Encoded']
        except Exception as e:
            if i == 4:
                log(f"Imagen API Error: {e}", error=True)
                return None
            time.sleep(2**i)
    return None

def upload_to_temp_host(filepath):
    """画像の公開URL化"""
    try:
        url = "https://freeimage.host/api/1/upload"
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
    """Printfulへの出品"""
    headers = {
        "Authorization": f"Bearer {PRINTFUL_API_KEY}",
        "X-PF-Store-Id": PRINTFUL_STORE_ID,
        "Content-Type": "application/json"
    }

    # 1. File Library への登録
    file_payload = {"role": "artwork", "url": public_url}
    file_res = requests.post("https://api.printful.com/files", headers=headers, json=file_payload, timeout=60)
    if file_res.status_code != 200:
        return {"error": f"File API Error: {file_res.text}"}
    
    file_id = file_res.json()['result']['id']

    # 2. Sync Product の作成
    product_payload = {
        "sync_product": {
            "name": seo_data["title"],
            "thumbnail": public_url
        },
        "sync_variants": [
            {
                "variant_id": VARIANT_ID,
                "retail_price": "7.99",
                "files": [{"id": file_id}]
            }
        ]
    }
    
    res = requests.post("https://api.printful.com/sync/products", headers=headers, json=product_payload, timeout=60)
    return res.json()

def notify_discord(title, public_url, error_msg=None):
    if not DISCORD_WEBHOOK_URL: return
    
    if error_msg:
        content = f"❌ **エラー発生:** {title}\n```{error_msg}```"
    else:
        content = f"🚀 **新商品出品!**\n**Title:** {title}\n**URL:** {public_url}"
        
    requests.post(DISCORD_WEBHOOK_URL, json={"content": content})

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    log("Pipeline Started")
    
    try:
        top_ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json").json()
    except Exception as e:
        log("Failed to fetch Hacker News", error=True)
        return
        
    success_count = 0
    
    for story_id in top_ids[:STICKER_LIMIT]:
        try:
            story = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json").json()
            hn_title = story.get('title')
            log(f"Processing: {hn_title}")

            # 1. 画像生成用プロンプト作成
            sys_prompt = f"Create a professional sticker design prompt for: '{hn_title}'. Style: Die-cut, vector art, white border, minimalist. Output ONLY the visual prompt."
            image_prompt = call_gemini_text(sys_prompt)
            if not image_prompt: continue
            
            # 2. 画像生成
            img_b64 = generate_sticker_image(image_prompt)
            if not img_b64: continue
            
            filepath = os.path.join(OUTPUT_DIR, f"{story_id}.png")
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(img_b64))

            # 3. 画像解析によるSEOメタデータ生成
            seo_data = call_gemini_vision_seo(filepath, hn_title)

            # 4. 公開URL化
            public_url = upload_to_temp_host(filepath)
            if not public_url: continue

            # 5. Printful出品
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

    log(f"Pipeline Completed. Success: {success_count}/{STICKER_LIMIT}")

if __name__ == "__main__":
    main()