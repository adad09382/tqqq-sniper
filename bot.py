import os
import sys
import time
from datetime import date
import pandas as pd
import requests
import yfinance as yf

LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CSV = os.path.join(_SCRIPT_DIR, "data", "QQQ_1d.csv")
_DEFAULT_TQQQ_CSV = os.path.join(_SCRIPT_DIR, "data", "TQQQ_1d.csv")
QQQ_CSV_PATH = os.environ.get("QQQ_CSV_PATH", _DEFAULT_CSV)
TQQQ_CSV_PATH = os.environ.get("TQQQ_CSV_PATH", _DEFAULT_TQQQ_CSV)

SMA_WINDOW = 200
OVERHEAT_THRESHOLD = 0.15


def send_line_message(msg: str) -> None:
    if not LINE_CHANNEL_TOKEN or not LINE_USER_ID:
        print("未設定 LINE_CHANNEL_TOKEN 或 LINE_USER_ID 環境變數")
        sys.exit(1)

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": msg}],
    }

    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                return
            print(f"LINE Messaging API 回應異常 (HTTP {response.status_code}): {response.text}")
        except requests.RequestException as e:
            print(f"第 {attempt + 1} 次發送失敗: {e}")
            if attempt < 2:
                time.sleep(3)

    print("LINE 訊息發送失敗，已重試 3 次")
    sys.exit(1)


def load_qqq_from_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.rename(columns={"close": "Close"})
    df = df[["timestamp", "Close"]].set_index("timestamp")
    return df


def load_qqq_from_yfinance() -> pd.DataFrame:
    for attempt in range(3):
        try:
            ticker = yf.Ticker("QQQ")
            df = ticker.history(period="2y")
            if not df.empty:
                return df[["Close"]]
        except Exception as e:
            print(f"yfinance 第 {attempt + 1} 次下載失敗: {e}")
            if attempt < 2:
                time.sleep(5)
    raise RuntimeError("yfinance 無法取得 QQQ 數據，已重試 3 次")


def main():
    if os.environ.get("DATA_UPDATE_FAILED"):
        send_line_message("\n⚠️ [警告] CSV 數據更新失敗，今日訊號可能使用舊數據，請手動確認。")
        return

    try:
        # 1. 載入數據（優先本地 CSV，否則使用 yfinance）
        if QQQ_CSV_PATH and os.path.exists(QQQ_CSV_PATH):
            print(f"使用本地 CSV: {QQQ_CSV_PATH}")
            df = load_qqq_from_csv(QQQ_CSV_PATH)
        else:
            print("使用 yfinance 下載 QQQ 數據...")
            df = load_qqq_from_yfinance()

        if len(df) < SMA_WINDOW:
            send_line_message(
                f"\n⚠️ [警告] QQQ 數據不足（僅 {len(df)} 筆，需 >= {SMA_WINDOW} 筆），請檢查數據來源。"
            )
            return

        # 檢查數據新鮮度：最新一筆不應超過 5 個日曆天前
        latest_date = df.index[-1].date()
        days_stale = (date.today() - latest_date).days
        if days_stale > 5:
            send_line_message(
                f"\n⚠️ [警告] QQQ 數據疑似過舊\n"
                f"最新一筆：{latest_date}（已 {days_stale} 天前）\n"
                f"請確認 update_data.py 是否正常運作。"
            )
            return

        # 2. 計算核心指標
        current_close = df["Close"].iloc[-1]
        sma200 = df["Close"].rolling(window=SMA_WINDOW).mean().iloc[-1]
        bias_ratio = (current_close - sma200) / sma200
        trade_date = df.index[-1].strftime("%Y-%m-%d")

        tqqq_close = None
        if os.path.exists(TQQQ_CSV_PATH):
            tqqq_df = load_qqq_from_csv(TQQQ_CSV_PATH)
            tqqq_close = tqqq_df["Close"].iloc[-1]

        # 3. 狀態機判定
        if current_close < sma200:
            state = "🚨 狀態一：絕對防禦\n👉 動作：0% TQQQ（全倉換回 QQQ 或現金）"
        elif bias_ratio >= OVERHEAT_THRESHOLD:
            state = "💰 狀態三：高檔過熱收割\n👉 動作：賣出一半 TQQQ（維持 50% TQQQ + 50% QQQ）"
        else:
            state = "🚀 狀態二：全速健康牛市\n👉 動作：100% 全倉 TQQQ"

        # 4. 組裝並發送訊息
        tqqq_line = f"\n💎 TQQQ 收盤: ${tqqq_close:.2f}" if tqqq_close else ""
        msg = (
            f"\n🤖 【TQQQ 狙擊手 - 每日確認】"
            f"\n📅 交易基準日: {trade_date}"
            f"\n📈 QQQ 收盤: ${current_close:.2f}"
            f"\n📏 200日均線: ${sma200:.2f}"
            f"\n📊 乖離率: {bias_ratio * 100:.2f}%"
            f"{tqqq_line}"
            f"\n----------------------"
            f"\n{state}"
        )
        send_line_message(msg)

    except Exception as e:
        send_line_message(f"\n❌ [錯誤] 機器人執行異常:\n{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
