import os
import pandas as pd
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.progress import track

console = Console()

def create_html(title, heat_score, context_tag):
    # タイトルが長い場合は省略
    display_title = title if len(title) < 65 else title[:62] + "..."
    
    # 物理ステッカー（ダイカット）風のモダンなHTML/CSSデザイン
    return f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <!-- 高品質なGoogle Fontsの読み込み -->
        <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&family=Inter:wght@700;900&display=swap" rel="stylesheet">
        <style>
            body {{ 
                margin: 0; 
                padding: 40px; 
                background: transparent; 
                display: flex; 
                align-items: flex-start; 
                justify-content: flex-start; 
            }}
            /* 白いフチと影（ダイカット加工のシミュレート） */
            .sticker-diecut {{
                background: white;
                padding: 10px;
                border-radius: 28px;
                filter: drop-shadow(0px 15px 25px rgba(0,0,0,0.4));
                display: inline-block;
                transform: rotate(-2deg); /* ステッカーを貼ったような傾き */
            }}
            /* 内側のコンテンツエリア（ダークグラデーション） */
            .sticker-inner {{
                background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
                border-radius: 20px;
                width: 500px;
                min-height: 240px;
                padding: 32px;
                font-family: 'Inter', sans-serif;
                position: relative;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .code-font {{ font-family: 'Fira Code', monospace; }}
            /* 背景の光彩エフェクト（グラスモーフィズム） */
            .glow-pink {{ position: absolute; top: -50px; right: -50px; width: 180px; height: 180px; background: #ec4899; filter: blur(60px); opacity: 0.5; border-radius: 50%; }}
            .glow-blue {{ position: absolute; bottom: -50px; left: -20px; width: 150px; height: 150px; background: #3b82f6; filter: blur(50px); opacity: 0.5; border-radius: 50%; }}
        </style>
    </head>
    <body>
        <div id="sticker-element" class="sticker-diecut">
            <div class="sticker-inner flex flex-col justify-between shadow-inner">
                <div class="glow-pink"></div><div class="glow-blue"></div>
                
                <!-- ヘッダー部分 -->
                <div class="relative z-10 flex justify-between items-start mb-6">
                    <span class="px-4 py-1.5 bg-white/10 rounded-full text-xs font-bold text-cyan-300 tracking-wider uppercase backdrop-blur-md border border-white/20 shadow-sm">
                        {context_tag}
                    </span>
                    <div class="flex items-center gap-1.5 bg-orange-500/20 text-orange-400 px-3 py-1.5 rounded-full border border-orange-500/30 backdrop-blur-md shadow-sm">
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1011.95-4.95c-.592-.591-.98-.985-1.348-1.467-.363-.476-.724-1.063-1.207-2.03zM12.12 15.12A3 3 0 017 13s.879.5 2.5.5c0-1 .5-4 1.25-4.5.5 1 .786 1.293 1.371 1.879A2.99 2.99 0 0113 13a2.99 2.99 0 01-.879 2.121z" clip-rule="evenodd"></path></svg>
                        <span class="font-black text-sm">{heat_score}</span>
                    </div>
                </div>
                
                <!-- メインタイトル -->
                <h1 class="relative z-10 text-2xl md:text-3xl font-black text-white leading-snug mb-8 drop-shadow-lg tracking-tight">
                    {display_title}
                </h1>
                
                <!-- フッター部分 -->
                <div class="relative z-10 flex items-center justify-between border-t border-white/10 pt-4 mt-auto">
                    <div class="code-font text-xs text-gray-300 flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-green-400 animate-pulse shadow-[0_0_8px_#4ade80]"></span>
                        TRENDING_NOW
                    </div>
                    <div class="text-[10px] font-black text-gray-400 tracking-widest opacity-80">
                        HACKER NEWS
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

def generate_images(df, output_dir="stickers_output"):
    if df.empty:
        console.print("[bold yellow][警告][/bold yellow] 生成対象のデータがありません。")
        return
        
    os.makedirs(output_dir, exist_ok=True)
        
    with sync_playwright() as p:
        console.print("[cyan]Playwrightを起動中...[/cyan]")
        browser = p.chromium.launch()
        page = browser.new_page()

        for index, row in track(df.iterrows(), total=len(df), description="[bold green]高品質ステッカー生成中..."):
            title = row['title']
            heat_score = row['heat_score']
            context_tag = row['context_tag']
            
            html_content = create_html(title, heat_score, context_tag)
            page.set_content(html_content)
            
            # Google FontsとTailwindの適用を確実にするため待機時間を少し長めに設定
            page.wait_for_selector("#sticker-element")
            page.wait_for_timeout(1500) 
            
            element = page.locator(".sticker-diecut")
            
            safe_title = "".join([c if c.isalnum() else "_" for c in title[:15]])
            filename = f"sticker_{heat_score}_{safe_title}.png"
            filepath = os.path.join(output_dir, filename)
            
            # omit_background=True により、白フチの外側は透過PNGになります
            element.screenshot(path=filepath, omit_background=True)
            
        browser.close()
        
        console.print(f"[bold green]'{output_dir}' フォルダに {len(df)} 枚の画像が保存されました。[/bold green]")