import os
import pandas as pd
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.progress import track
from datetime import datetime

console = Console()

def create_html(title, heat_score, context_tag):
    # タイトルの長さを調整
    display_title = title if len(title) < 60 else title[:57] + "..."
    current_date = datetime.now().strftime("%Y.%m.%d")
    
    # プレミアム・ネオンデザイン（物理ステッカー風の白いフチ＋ネオン発光）
    return f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=JetBrains+Mono:wght@500&family=Inter:wght@900&display=swap" rel="stylesheet">
        <style>
            body {{ 
                margin: 0; padding: 50px; background: transparent; 
            }}
            .diecut-wrapper {{
                background: white;
                padding: 12px;
                border-radius: 35px;
                display: inline-block;
                filter: drop-shadow(0 20px 30px rgba(0,0,0,0.5));
                transform: rotate(-1.5deg);
            }}
            .main-card {{
                background: #050505;
                border-radius: 25px;
                width: 520px;
                min-height: 260px;
                padding: 35px;
                font-family: 'Inter', sans-serif;
                position: relative;
                overflow: hidden;
                border: 2px solid #1a1a1a;
            }}
            .neon-border {{
                position: absolute; top: 0; left: 0; width: 100%; height: 5px;
                background: linear-gradient(90deg, #00f2fe, #4facfe, #00f2fe);
                box-shadow: 0 0 15px #4facfe;
            }}
            .context-badge {{
                font-family: 'JetBrains Mono', monospace;
                background: rgba(79, 172, 254, 0.15);
                color: #00f2fe;
                border: 1px solid rgba(0, 242, 254, 0.3);
                text-shadow: 0 0 8px #00f2fe;
            }}
            .score-glow {{
                font-family: 'Orbitron', sans-serif;
                background: linear-gradient(45deg, #f093fb 0%, #f5576c 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                filter: drop-shadow(0 0 5px rgba(245, 87, 108, 0.5));
            }}
        </style>
    </head>
    <body>
        <div id="sticker-element" class="diecut-wrapper">
            <div class="main-card flex flex-col justify-between">
                <div class="neon-border"></div>
                
                <div class="flex justify-between items-center mb-6">
                    <span class="context-badge px-4 py-1 rounded-md text-xs font-bold tracking-tighter">
                        TAG::{context_tag}
                    </span>
                    <div class="flex items-center gap-2">
                        <span class="text-[10px] text-gray-500 font-bold tracking-widest">HEAT_LEVEL</span>
                        <span class="score-glow text-xl font-black">{heat_score}</span>
                    </div>
                </div>

                <h1 class="text-white text-3xl font-black leading-tight tracking-tighter mb-8 italic">
                    {display_title}
                </h1>

                <div class="flex justify-between items-end border-t border-white/5 pt-4">
                    <div class="flex flex-col">
                        <span class="text-[9px] text-gray-600 font-bold uppercase tracking-[0.2em]">Deployment Date</span>
                        <span class="text-[11px] text-gray-400 font-mono tracking-tighter">{current_date}</span>
                    </div>
                    <div class="text-[10px] text-white font-black bg-white/5 px-3 py-1 rounded border border-white/10 italic">
                        v2.0_PREMIUM
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

def generate_images(df, output_dir="stickers_output"):
    if df.empty:
        console.print("[yellow]No data to generate stickers.[/yellow]")
        return
        
    os.makedirs(output_dir, exist_ok=True)
        
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        for index, row in track(df.iterrows(), total=len(df), description="[bold magenta]PREMIUMステッカー生成中..."):
            title = row['title']
            heat_score = row['heat_score']
            context_tag = row['context_tag']
            
            html_content = create_html(title, heat_score, context_tag)
            page.set_content(html_content)
            
            # フォント読み込み時間を確保
            page.wait_for_selector("#sticker-element")
            page.wait_for_timeout(2000) 
            
            element = page.locator(".diecut-wrapper")
            
            safe_title = "".join([c if c.isalnum() else "_" for c in title[:15]])
            filename = f"premium_{heat_score}_{safe_title}.png"
            filepath = os.path.join(output_dir, filename)
            
            element.screenshot(path=filepath, omit_background=True)
            
        browser.close()
        console.print(f"[bold green]Success: {len(df)} images saved to '{output_dir}'[/bold green]")