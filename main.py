import os
import json
import base64
import requests
import time
import re
import urllib.parse
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

# Printful Settings
VARIANT_ID = 3559 

def log(msg, error=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = "[ERROR]" if error else "[INFO]"
    print(f"{timestamp} {prefix} {msg}")

def load_endpoints():
    """外部設定ファイルからAPIエンドポイントを読み込む"""
    try:
        with open("endpoints.json", "r") as f:
            return json.load(f)
    except Exception as e:
        log(f"Failed to load endpoints.json: {e}", error=True)
        # フォールバック用のデフォルトURL（エラー回避用）
        return {
            "gemini": "[https://generativelanguage.googleapis.com](https://generativelanguage.googleapis.com)",
            "pollinations": "[https://image.pollinations.ai](https://image.pollinations.ai)",
            "freeimage": "[https://freeimage.host](https://freeimage.host)",
            "printful": "[https://api.printful.com](https://api.printful.com)",
            "hacker_news": "[https://hacker-news.firebaseio.com](https://hacker-news.firebaseio.com)"
        }

ENDPOINTS = load_endpoints()

def call_gemini_text(prompt):
    """Gemini 1.5 Flash (テキスト生成 - REST API版)"""
    base_url = ENDPOINTS.get("gemini")
    url = f"{base_url}/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        res = requests.post(url, json=payload, timeout=30)
        res.raise_for_status()
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        log(f"Gemini Text API Error: {e}", error=True)
        return None

def call_gemini_vision_seo(img_path, hn_title):
    """Gemini 1.5 Flash (画像解析 + SEO生成 - REST API版)"""
    base_url = ENDPOINTS.get("gemini")
    url = f"{base_url}/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
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
        
        res = requests.post(url, json=payload, timeout=30)
        res.raise_for_status()
        text = res.json()['candidates'][0]['content']['parts'][0]['text']
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else json.loads(text)
    except Exception as e:
        log(f"SEO Generation Error: {e}", error=True)
        return {"title": f"Tech Trend Sticker: {hn_title[:20]}", "description": hn_title, "tags": ["tech"]}

def generate_sticker_image(prompt):
    """無料の画像生成APIを使用して画像を生成"""
    try:
        encoded_prompt = urllib.parse.quote(prompt + " sticker design, die-cut, white background, vector art")
        base_url = ENDPOINTS.get("pollinations")
        url = f"{base_url}/prompt/{encoded_prompt}?width=512&height=512&nologo=true"
        
        res = requests.get(url, timeout=60)
        if res.status_code == 200:
            return base64.b64encode(res.content).decode('utf-8')
        else:
            log(f"Image API Error: {res.status_code}", error=True)
            return None
    except Exception as e:
        log(f"Image Generation Error: {e}", error=True)
        return None

def upload_to_temp_host(filepath):
    """画像の公開URL化"""
    try:
        base_url = ENDPOINTS.get("freeimage")
        url = f"{base_url}/api/1/upload"
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

    base_url = ENDPOINTS.get("printful")
    
    file_payload = {"role": "artwork", "url": public_url}
    file_res = requests.post(f"{base_url}/files", headers=headers, json=file_payload, timeout=60)
    if file_res.status_code != 200:
        return {"error": f"File API Error: {file_res.text}"}
    
    file_id = file_res.json()['result']['id']

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
    
    res = requests.post(f"{base_url}/sync/products", headers=headers, json=product_payload, timeout=60)
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
    
    base_url = ENDPOINTS.get("hacker_news")
    
    try:
        hn_url = f"{base_url}/v0/topstories.json"
        top_ids = requests.get(hn_url).json()
    except Exception as e:
        log(f"Failed to fetch Hacker News: {e}", error=True)
        return
        
    success_count = 0
    
    for story_id in top_ids[:STICKER_LIMIT]:
        try:
            item_url = f"{base_url}/v0/item/{story_id}.json"
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
            if not img_b64: 
                log("Failed to generate image", error=True)
                continue
            
            filepath = os.path.join(OUTPUT_DIR, f"{story_id}.png")
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(img_b64))

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
