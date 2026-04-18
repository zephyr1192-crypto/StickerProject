import typer
import pandas as pd
import requests
import time
from rich.console import Console
from rich.progress import track
from feedback_manager import add_negative_word

app = typer.Typer()
console = Console()
HN_BASE_URL = "https://hacker-news.firebaseio.com/v0"

def fetch_top_story_ids(limit: int):
    url = f"{HN_BASE_URL}/topstories.json"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()[:limit]

def fetch_story_details(story_ids):
    stories = []
    for story_id in track(story_ids, description="[cyan]Hacker News記事を取得中..."):
        url = f"{HN_BASE_URL}/item/{story_id}.json"
        for _ in range(3):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                if data and data.get("type") == "story":
                    stories.append({
                        "id": data.get("id"),
                        "title": data.get("title", ""),
                        "score": data.get("score", 0),
                        "descendants": data.get("descendants", 0),
                        "time": data.get("time", 0),
                        "url": data.get("url", "")
                    })
                break
            except requests.exceptions.RequestException:
                time.sleep(1)
        time.sleep(0.05)
    return stories

def assign_context(title):
    title_lower = title.lower()
    if any(word in title_lower for word in ['ai', 'gpt', 'llm', 'openai', 'claude']): return 'AI'
    elif any(word in title_lower for word in ['crypto', 'bitcoin', 'btc', 'startup', 'vc', 'fund']): return 'Finance'
    elif any(word in title_lower for word in ['linux', 'rust', 'python', 'github', 'db']): return 'Core Tech'
    return 'Other'

def run_scraper(limit: int, output_file: str):
    """メインのスクレイピング処理。他ファイルから呼び出される。"""
    story_ids = fetch_top_story_ids(limit=limit * 3)
    stories_data = fetch_story_details(story_ids)
    
    if not stories_data:
        console.print("[red]データが取得できませんでした。[/red]")
        return False

    df = pd.DataFrame(stories_data)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    df['heat_score'] = df['score'] + df['descendants']
    df_sorted = df.sort_values(by='heat_score', ascending=False)
    df_sorted['context_tag'] = df_sorted['title'].apply(assign_context)
    
    df_final = df_sorted.head(limit)
    df_final.to_csv(output_file, index=False, encoding='utf-8')
    console.print(f"[green]トレンドデータを '{output_file}' に保存しました。({len(df_final)}件)[/green]")
    return True

@app.command("scrape")
def scrape_cmd(limit: int = 5, output_file: str = "hn_trends_analyzed.csv"):
    """手動でスクレイピングのみを実行するコマンド"""
    run_scraper(limit, output_file)

@app.command("ban")
def ban_word(word: str, reason: str = typer.Option("Not suitable for stickers", help="Reason for banning")):
    """指定したワードを負のデータとして学習させ、今後の生成から除外する"""
    add_negative_word(word, reason)

if __name__ == "__main__":
    app()