# %% [markdown]
# # Hacker News トレンド分析 (Interactive Window対応版)
# コードの区切りにある「Run Cell」を上から順番にクリックしていくことで、
# 途中のデータ（Pandasデータフレーム等）を視覚的に確認しながら開発できます。

# %%
import requests
import pandas as pd
import time

HN_BASE_URL = "https://hacker-news.firebaseio.com/v0"

def fetch_top_story_ids(limit=50):
    print(f"Hacker Newsのトップ記事IDを取得中 (最大 {limit} 件)...")
    url = f"{HN_BASE_URL}/topstories.json"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()[:limit]

# --- セルごとの実行確認 ---
# 取得件数を絞ってテスト実行
story_ids = fetch_top_story_ids(limit=10)

# 変数を最後に単独で記述すると、右側のウィンドウに中身が出力されます
story_ids 

# %%
def fetch_story_details(story_ids):
    stories = []
    total = len(story_ids)
    print(f"{total} 件の記事詳細を取得します...")
    
    for i, story_id in enumerate(story_ids, 1):
        url = f"{HN_BASE_URL}/item/{story_id}.json"
        
        for attempt in range(3):
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
                time.sleep(2)
                
        time.sleep(0.1)
    return stories

# --- セルごとの実行確認 ---
stories_data = fetch_story_details(story_ids)

# 最初の2件だけ中身を確認
stories_data[:2] 

# %%
def process_and_analyze(stories):
    if not stories:
        return pd.DataFrame()

    df = pd.DataFrame(stories)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    df['heat_score'] = df['score'] + df['descendants']
    df_sorted = df.sort_values(by='heat_score', ascending=False)
    df_sorted['title_lower'] = df_sorted['title'].str.lower()
    
    def assign_context(title):
        if any(word in title for word in ['ai', 'gpt', 'llm', 'openai', 'claude']): return 'AI'
        elif any(word in title for word in ['crypto', 'bitcoin', 'btc', 'startup', 'vc', 'fund']): return 'Finance/Startup'
        elif any(word in title for word in ['linux', 'rust', 'python', 'github', 'db']): return 'Core Tech'
        return 'Other'

    df_sorted['context_tag'] = df_sorted['title_lower'].apply(assign_context)
    columns_to_keep = ['id', 'datetime', 'title', 'score', 'descendants', 'heat_score', 'context_tag', 'url']
    return df_sorted[columns_to_keep]

# --- セルごとの実行確認 ---
analyzed_df = process_and_analyze(stories_data)

# 【重要】ここでPandasデータフレームを呼び出すと、
# VS Code上でExcelのような表形式で表示され、ソートやフィルタリングが直感的に行えます。
analyzed_df

# %%
# 最後にCSVとして保存 (必要な時だけこのセルを実行します)
output_file = "hn_trends_analyzed.csv"
analyzed_df.to_csv(output_file, index=False, encoding='utf-8')
print(f"分析データを '{output_file}' に保存しました。")
# %%
