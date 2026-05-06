# TQQQ Daily Sniper Bot

基於 QQQ 200 日均線與乖離率的每日倉位確認機器人，透過 LINE Notify 發送操作指令。

## 策略邏輯

| 條件 | 狀態 | 行動 |
|------|------|------|
| QQQ < SMA200 | 🚨 絕對防禦 | 0% TQQQ，持有 QQQ 或現金 |
| QQQ ≥ SMA200 且乖離率 < 15% | 🚀 健康牛市 | 100% TQQQ |
| QQQ ≥ SMA200 且乖離率 ≥ 15% | 💰 過熱收割 | 50% TQQQ + 50% QQQ |

## 本地執行

```bash
pip install -r requirements.txt

# 使用 yfinance（預設）
LINE_TOKEN=your_token python bot.py

# 使用本地 CSV（可選，需有 timestamp/close 欄位）
QQQ_CSV_PATH=/path/to/QQQ_1d.csv LINE_TOKEN=your_token python bot.py
```

## 部署到 GitHub Actions

### 步驟一：建立 GitHub Repository

```bash
git init
git add .
git commit -m "init: TQQQ Sniper Bot"
git remote add origin https://github.com/<你的帳號>/tqqq-sniper.git
git push -u origin main
```

### 步驟二：設定 LINE_TOKEN Secret

1. 前往你的 GitHub Repository 頁面
2. 點選 **Settings** → 左側選單 **Secrets and variables** → **Actions**
3. 點選 **New repository secret**
4. Name 填入 `LINE_TOKEN`，Secret 填入你的 LINE Notify Token
5. 點選 **Add secret**

### 步驟三：取得 LINE Notify Token

1. 前往 [LINE Notify](https://notify-bot.line.me/my/)，登入你的 LINE 帳號
2. 點選 **發行權杖 (Generate token)**
3. 填入權杖名稱（如 `TQQQ Bot`），選擇要推送的聊天室
4. 複製產生的 Token，貼入 GitHub Secrets

### 步驟四：驗證 Actions 執行

1. 前往 Repository → **Actions** 頁籤
2. 選擇 **TQQQ Daily Sniper Bot**
3. 點選 **Run workflow** 手動觸發，確認執行成功並收到 LINE 通知

## 排程

- 自動執行：每週一至週五 UTC 12:00（台灣時間晚上 8:00）
- 手動執行：在 GitHub Actions 頁面點選 `Run workflow`

## 環境變數

| 變數 | 必填 | 說明 |
|------|------|------|
| `LINE_TOKEN` | ✅ | LINE Notify 存取權杖 |
| `QQQ_CSV_PATH` | ❌ | 本地 QQQ CSV 檔案路徑（留空則使用 yfinance） |
