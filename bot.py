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
        print("未設定 LINE_CHANNEL_TOKEN 或 LINE_USER_ID")
        sys.exit(1)
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": msg}]}
    for attempt in range(3):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            if r.status_code == 200:
                return
            print(f"LINE API 異常 ({r.status_code}): {r.text}")
        except requests.RequestException as e:
            print(f"第 {attempt + 1} 次失敗: {e}")
            if attempt < 2:
                time.sleep(3)
    print("LINE 發送失敗，已重試 3 次")
    sys.exit(1)


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df.rename(columns={"close": "Close"})
    return df[["timestamp", "Close"]].set_index("timestamp")


def load_from_yfinance() -> pd.DataFrame:
    for attempt in range(3):
        try:
            df = yf.Ticker("QQQ").history(period="2y")
            if not df.empty:
                return df[["Close"]]
        except Exception as e:
            print(f"yfinance 第 {attempt + 1} 次失敗: {e}")
            if attempt < 2:
                time.sleep(5)
    raise RuntimeError("yfinance 無法取得數據，已重試 3 次")


def get_state(close: float, sma200: float) -> int:
    if close < sma200:
        return 1
    if (close - sma200) / sma200 >= OVERHEAT_THRESHOLD:
        return 3
    return 2


def count_consecutive(df: pd.DataFrame, sma_series: pd.Series, target_state: int) -> int:
    valid_sma = sma_series.dropna()
    valid_closes = df["Close"].loc[valid_sma.index]
    count = 0
    for i in range(len(valid_sma) - 1, -1, -1):
        if get_state(valid_closes.iloc[i], valid_sma.iloc[i]) == target_state:
            count += 1
        else:
            break
    return count


def build_message(
    trade_date, current_close, sma200, bias_ratio, tqqq_close,
    current_state, prev_state, consecutive_days,
) -> str:
    state_changed = current_state != prev_state

    overheat_price = sma200 * (1 + OVERHEAT_THRESHOLD)
    pct_to_overheat = (overheat_price - current_close) / current_close * 100
    pct_to_bear = (sma200 - current_close) / current_close * 100

    STATE_EMOJI = {1: "🚨", 2: "🚀", 3: "💰"}
    STATE_NAME = {
        1: "狀態一：絕對防禦",
        2: "狀態二：全速健康牛市",
        3: "狀態三：高檔過熱收割",
    }
    TRANSITION_HEADER = {
        (1, 2): "🟢🟢🟢 牛市進場訊號！State 1 → 2",
        (3, 2): "🟢🟢🟢 回落進場訊號！State 3 → 2",
        (2, 3): "🔴🔴🔴 過熱警告！State 2 → 3",
        (1, 3): "🔴🔴🔴 跳升過熱！State 1 → 3",
        (2, 1): "🚨🚨🚨 緊急熊市！State 2 → 1",
        (3, 1): "🚨🚨🚨 緊急熊市！State 3 → 1",
    }

    if state_changed:
        if current_state == 2:
            action = "👉 【進場】建倉 100% TQQQ"
        elif current_state == 3:
            action = "👉 【減倉】賣出一半 TQQQ → 50% TQQQ + 50% QQQ"
        else:
            action = "👉 【緊急清倉】立即賣出所有 TQQQ"
    else:
        if current_state == 1:
            action = "👉 持現金 / QQQ，等待收復 SMA200"
        elif current_state == 2:
            action = "👉 無新訊號，等待下次轉換（State 1→2 或 3→2）再進場"
        else:
            action = "👉 維持 50% TQQQ + 50% QQQ，等待回落訊號"

    if current_state == 1:
        key_prices = (
            f"\n📍 關鍵價位"
            f"\n🟢 牛市進場：QQQ 站回 ${sma200:.2f}（需漲 {abs(pct_to_bear):.1f}%）"
        )
    elif current_state == 2:
        key_prices = (
            f"\n📍 關鍵價位"
            f"\n🔴 過熱賣出：QQQ > ${overheat_price:.2f}（再漲 {pct_to_overheat:.1f}%）"
            f"\n⚫ 熊市出場：QQQ < ${sma200:.2f}（需跌 {abs(pct_to_bear):.1f}%）"
        )
    else:
        key_prices = (
            f"\n📍 關鍵價位"
            f"\n🟢 回落進場：QQQ < ${overheat_price:.2f}（需跌 {abs(pct_to_overheat):.1f}%）"
            f"\n⚫ 熊市全出：QQQ < ${sma200:.2f}（需跌 {abs(pct_to_bear):.1f}%）"
        )

    header = f"\n{TRANSITION_HEADER.get((prev_state, current_state), '')}\n" if state_changed else ""
    tqqq_line = f"\n💎 TQQQ 收盤: ${tqqq_close:.2f}" if tqqq_close else ""

    return (
        f"{header}"
        f"\n🤖 【TQQQ 狙擊手 - 每日確認】"
        f"\n📅 交易基準日: {trade_date}"
        f"\n📈 QQQ 收盤: ${current_close:.2f}"
        f"\n📏 200日均線: ${sma200:.2f}"
        f"\n📊 乖離率: {bias_ratio * 100:.2f}%"
        f"{tqqq_line}"
        f"\n----------------------"
        f"\n{STATE_EMOJI[current_state]} {STATE_NAME[current_state]}（持續 {consecutive_days} 天）"
        f"\n{action}"
        f"{key_prices}"
    )


def main():
    if os.environ.get("DATA_UPDATE_FAILED"):
        send_line_message("⚠️ [警告] CSV 數據更新失敗，今日訊號暫停，請手動確認。")
        return

    try:
        if QQQ_CSV_PATH and os.path.exists(QQQ_CSV_PATH):
            df = load_csv(QQQ_CSV_PATH)
        else:
            df = load_from_yfinance()

        if len(df) < SMA_WINDOW + 1:
            send_line_message(f"⚠️ 數據不足（{len(df)} 筆），需至少 {SMA_WINDOW + 1} 筆。")
            return

        latest_date = df.index[-1].date()
        if (date.today() - latest_date).days > 5:
            send_line_message(f"⚠️ 數據過舊（最後：{latest_date}），請確認更新。")
            return

        sma_series = df["Close"].rolling(window=SMA_WINDOW).mean()
        current_close = df["Close"].iloc[-1]
        sma200 = sma_series.iloc[-1]
        prev_sma200 = sma_series.iloc[-2]
        bias_ratio = (current_close - sma200) / sma200
        trade_date = df.index[-1].strftime("%Y-%m-%d")

        current_state = get_state(current_close, sma200)
        prev_state = get_state(df["Close"].iloc[-2], prev_sma200)
        consecutive_days = count_consecutive(df, sma_series, current_state)

        tqqq_close = None
        if os.path.exists(TQQQ_CSV_PATH):
            tqqq_close = load_csv(TQQQ_CSV_PATH)["Close"].iloc[-1]

        msg = build_message(
            trade_date, current_close, sma200, bias_ratio, tqqq_close,
            current_state, prev_state, consecutive_days,
        )
        send_line_message(msg)

    except Exception as e:
        send_line_message(f"❌ [錯誤] 執行異常:\n{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
