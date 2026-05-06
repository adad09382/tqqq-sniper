import os
import time
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SYMBOLS = {
    "QQQ": os.path.join(SCRIPT_DIR, "data", "QQQ_1d.csv"),
    "TQQQ": os.path.join(SCRIPT_DIR, "data", "TQQQ_1d.csv"),
}


def load_existing_dates(csv_path: str) -> set:
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    return set(df["timestamp"].dt.date)


def fetch_missing(symbol: str, start: date, end: date) -> pd.DataFrame:
    for attempt in range(3):
        try:
            df = yf.Ticker(symbol).history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                auto_adjust=True,
            )
            if not df.empty:
                return df
        except Exception as e:
            print(f"  [{symbol}] 第 {attempt + 1} 次下載失敗: {e}")
            if attempt < 2:
                time.sleep(5)
    return pd.DataFrame()


def format_rows(df: pd.DataFrame, symbol: str, existing_dates: set) -> pd.DataFrame:
    rows = []
    for ts, row in df.iterrows():
        row_date = ts.date()
        if row_date in existing_dates:
            continue
        rows.append({
            "timestamp": ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "symbol": symbol,
            "open": round(row["Open"], 6),
            "high": round(row["High"], 6),
            "low": round(row["Low"], 6),
            "close": round(row["Close"], 6),
            "volume": int(row["Volume"]),
            "timeframe": "1d",
        })
    return pd.DataFrame(rows)


def update_symbol(symbol: str, csv_path: str) -> int:
    existing_dates = load_existing_dates(csv_path)
    latest_date = max(existing_dates)
    start = latest_date + timedelta(days=1)
    today = date.today()

    if start > today:
        print(f"[{symbol}] 已是最新（最後一筆：{latest_date}），跳過。")
        return 0

    print(f"[{symbol}] 補抓 {start} ～ {today}...")
    raw = fetch_missing(symbol, start, today)

    if raw.empty:
        print(f"[{symbol}] 無新數據（可能為假日或休市）。")
        return 0

    new_rows = format_rows(raw, symbol, existing_dates)

    if new_rows.empty:
        print(f"[{symbol}] 所有日期已存在，無需寫入。")
        return 0

    new_rows.to_csv(csv_path, mode="a", header=False, index=False)
    print(f"[{symbol}] 新增 {len(new_rows)} 筆：{sorted(new_rows['timestamp'].tolist())}")
    return len(new_rows)


def main():
    total = 0
    for symbol, csv_path in SYMBOLS.items():
        if not os.path.exists(csv_path):
            print(f"[{symbol}] 找不到 CSV：{csv_path}，跳過。")
            continue
        total += update_symbol(symbol, csv_path)

    print(f"\n完成，共新增 {total} 筆數據。")


if __name__ == "__main__":
    main()
