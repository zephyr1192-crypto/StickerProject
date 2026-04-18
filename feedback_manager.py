import os
import pandas as pd
from rich.console import Console

console = Console()
NEGATIVE_CSV = "negative_feedback.csv"

def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """単語の集合を用いた単純かつ高速な類似度計算（Jaccard係数）"""
    set1 = set(str(text1).lower().split())
    set2 = set(str(text2).lower().split())
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union

def apply_negative_feedback(df: pd.DataFrame, penalty_score: int = -500, threshold: float = 0.3) -> pd.DataFrame:
    """負のデータと類似しているトレンドのスコアを減点する"""
    if not os.path.exists(NEGATIVE_CSV):
        return df # 負のデータがまだ無い場合はそのまま返す
        
    neg_df = pd.read_csv(NEGATIVE_CSV)
    if neg_df.empty:
        return df

    console.print(f"[cyan]Applying negative feedback from {len(neg_df)} records...[/cyan]")
    
    def get_penalty(title):
        # 過去のNGワードリストと総当たりで類似度を計算し、最大値を求める
        max_sim = 0.0
        for neg_word in neg_df['word']:
            sim = calculate_jaccard_similarity(title, neg_word)
            if sim > max_sim:
                max_sim = sim
        # 類似度が閾値を超えていれば減点ペナルティを課す
        return penalty_score if max_sim >= threshold else 0

    # スコアの再計算（Pandasのベクトル演算的な適用）
    df['heat_score'] = df['heat_score'] + df['title'].apply(get_penalty)
    
    # スコア順に並び替え直し
    df = df.sort_values(by='heat_score', ascending=False).reset_index(drop=True)
    return df

def add_negative_word(word: str, reason: str = "manual"):
    """人間が「売れない」と判断したワードを負のデータとして学習させる"""
    new_data = pd.DataFrame([{"word": word, "reason": reason}])
    
    if os.path.exists(NEGATIVE_CSV):
        neg_df = pd.read_csv(NEGATIVE_CSV)
        # 重複チェック
        if word in neg_df['word'].values:
            console.print(f"[yellow]'{word}' is already in negative feedback list.[/yellow]")
            return
        neg_df = pd.concat([neg_df, new_data], ignore_index=True)
    else:
        neg_df = new_data
        
    neg_df.to_csv(NEGATIVE_CSV, index=False)
    console.print(f"[bold red]Negative feedback added: '{word}'[/bold red]")