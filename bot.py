import os
import sys
import time
import pandas as pd
import requests
import yfinance as yf

LINE_TOKEN = os.environ.get("LINE_TOKEN")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CSV = os.path.join(_SCRIPT_DIR, "data", "QQQ_1d.csv")
QQQ_CSV_PATH = os.environ.get("QQQ_CSV_PATH", _DEFAULT_CSV)

SMA_WINDOW = 200
OVERHEAT_THRESHOLD = 0.15


def send_line_notify(msg: str) -> None:
    if not LINE_TOKEN:
        print("未設定 LINE_TOKEN 環境變數")
        sys.exit(1)

    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}"}
    data = {"message": msg}

    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            if response.status_code == 200:
                return
            print(f"LINE Notify 回應異常 (HTTP {response.status_code}): {response.text}")
        except requests.RequestException as e:
            print(f"第 {attempt + 1} 次發送失敗: {e}")
            if attempt < 2:
                time.sleep(3)

    print("LINE Notify 發送失敗，已重試 3 次")
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
        send_line_notify("\n⚠️ [警告] CSV 數據更新失敗，今日訊號可能使用舊數據，請手動確認。")
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
            send_line_notify(
                f"\n⚠️ [警告] QQQ 數據不足（僅 {len(df)} 筆，需 >= {SMA_WINDOW} 筆），請檢查數據來源。"
            )
            return

        # 2. 計算核心指標
        current_close = df["Close"].iloc[-1]
        sma200 = df["Close"].rolling(window=SMA_WINDOW).mean().iloc[-1]
        bias_ratio = (current_close - sma200) / sma200
        trade_date = df.index[-1].strftime("%Y-%m-%d")

        # 3. 狀態機判定
        if current_close < sma200:
            state = "🚨 狀態一：絕對防禦\n👉 動作：0% TQQQ（全倉換回 QQQ 或現金）"
        elif bias_ratio >= OVERHEAT_THRESHOLD:
            state = "💰 狀態三：高檔過熱收割\n👉 動作：賣出一半 TQQQ（維持 50% TQQQ + 50% QQQ）"
        else:
            state = "🚀 狀態二：全速健康牛市\n👉 動作：100% 全倉 TQQQ"

        # 4. 組裝並發送訊息
        msg = (
            f"\n🤖 【TQQQ 狙擊手 - 每日確認】"
            f"\n📅 交易基準日: {trade_date}"
            f"\n📈 QQQ 收盤: ${current_close:.2f}"
            f"\n📏 200日均線: ${sma200:.2f}"
            f"\n📊 乖離率: {bias_ratio * 100:.2f}%"
            f"\n----------------------"
            f"\n{state}"
        )
        send_line_notify(msg)

    except Exception as e:
        send_line_notify(f"\n❌ [錯誤] 機器人執行異常:\n{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
