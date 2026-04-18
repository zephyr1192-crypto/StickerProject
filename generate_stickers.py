import os
import pandas as pd
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.progress import track

console = Console()

# HTMLテンプレート（ITエンジニア向けターミナル風デザイン Tailwind使用）
def create_html(title, heat_score, context_tag):
    display_title = title if len(title) < 50 else title[:47] + "..."
    
    return f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body {{ font-family: 'Courier New', Courier, monospace; background: transparent; margin: 0; padding: 20px; }}
        </style>
    </head>
    <body>
        <div id="sticker-element" class="w-[500px] h-[250px] bg-slate-900 text-green-400 p-8 rounded-2xl border-4 border-slate-700 shadow-[0_10px_30px_rgba(0,0,0,0.5)] flex flex-col justify-between relative overflow-hidden">
            <div class="flex items-center mb-4">
                <div class="w-4 h-4 rounded-full bg-red-500 mr-2 shadow-[0_0_8px_rgba(239,68,68,0.6)]"></div>
                <div class="w-4 h-4 rounded-full bg-yellow-500 mr-2 shadow-[0_0_8px_rgba(234,179,8,0.6)]"></div>
                <div class="w-4 h-4 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
                <span class="ml-4 text-xs text-slate-500 tracking-widest font-bold">~/{context_tag}/logs</span>
            </div>
            
            <div class="text-2xl font-bold leading-relaxed">
                <span class="text-pink-500 mr-2">❯</span>{display_title}
            </div>
            
            <div class="flex justify-between items-end border-t border-slate-800 pt-4 mt-4">
                <div class="text-xs text-slate-500">
                    STATUS: <span class="text-blue-400">TRENDING</span>
                </div>
                <div class="text-xs text-slate-500 font-bold bg-slate-800 px-3 py-1 rounded">
                    HEAT: <span class="text-orange-500">{heat_score}</span>
                </div>
            </div>
            
            <div class="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:20px_20px] pointer-events-none opacity-20"></div>
        </div>
    </body>
    </html>
    """

def generate_images(df, output_dir="stickers_output"):
    """
    データフレームからステッカー画像を生成する。
    main.py等から呼び出されることを前提とする。
    """
    if df.empty:
        console.print("[bold yellow][警告][/bold yellow] 生成対象のデータがありません。")
        return
        
    os.makedirs(output_dir, exist_ok=True)
        
    with sync_playwright() as p:
        console.print("[cyan]Playwrightを起動中...[/cyan]")
        browser = p.chromium.launch()
        page = browser.new_page()

        for index, row in track(df.iterrows(), total=len(df), description="[bold green]画像生成中..."):
            title = row['title']
            heat_score = row['heat_score']
            context_tag = row['context_tag']
            
            html_content = create_html(title, heat_score, context_tag)
            page.set_content(html_content)
            
            page.wait_for_selector("#sticker-element")
            page.wait_for_timeout(1000)
            
            element = page.locator("#sticker-element")
            
            safe_title = "".join([c if c.isalnum() else "_" for c in title[:15]])
            filename = f"sticker_{heat_score}_{safe_title}.png"
            filepath = os.path.join(output_dir, filename)
            
            element.screenshot(path=filepath, omit_background=True)
            
        browser.close()
        
        console.print(f"[bold green]'{output_dir}' フォルダに {len(df)} 枚の画像が保存されました。[/bold green]")