# TQQQ Daily Sniper Bot

基於 QQQ 200 日均線與乖離率的每日倉位確認機器人，透過 LINE Notify 發送操作指令。

## 策略邏輯

| 條件 | 狀態 | 行動 |
|------|------|------|
| QQQ < SMA200 | 🚨 絕對防禦 | 0% TQQQ，持有 QQQ 或現金 |
| QQQ ≥ SMA200 且乖離率 < 15% | 🚀 健康牛市 | 100% TQQQ |
| QQQ ≥ SMA200 且乖離率 ≥ 15% | 💰 過熱收割 | 50% TQQQ + 50% QQQ |

## 每日自動流程

```
GitHub Actions 觸發（每週一至週五 UTC 12:00）
        ↓
update_data.py
  讀 data/QQQ_1d.csv & TQQQ_1d.csv 最後一筆日期
  補抓缺漏的交易日（yfinance）
  git commit & push 回 repo
        ↓
bot.py
  讀 data/QQQ_1d.csv → 計算 SMA200 / 乖離率 → LINE Notify
```

## 本地執行

```bash
pip install -r requirements.txt

# 預設讀取 data/QQQ_1d.csv（repo 內已附歷史數據）
LINE_TOKEN=your_token python bot.py

# 指定其他 CSV 路徑
QQQ_CSV_PATH=/path/to/QQQ_1d.csv LINE_TOKEN=your_token python bot.py

# 手動更新本地 CSV（補抓最新數據）
python update_data.py
```

## 部署到 GitHub Actions

### 步驟一：建立 GitHub Repository 並推送

```bash
git init
git add .
git commit -m "init: TQQQ Sniper Bot"
git remote add origin https://github.com/<你的帳號>/tqqq-sniper.git
git push -u origin main
```

### 步驟二：開啟 Actions Write 權限

GitHub Actions 需要將更新後的 CSV 寫回 repo：

1. 前往 Repository → **Settings** → **Actions** → **General**
2. 滾動到 **Workflow permissions**
3. 選擇 **Read and write permissions**
4. 點選 **Save**

### 步驟三：設定 LINE_TOKEN Secret

1. 前往 Repository → **Settings** → **Secrets and variables** → **Actions**
2. 點選 **New repository secret**
3. Name 填入 `LINE_TOKEN`，Secret 填入你的 LINE Notify Token
4. 點選 **Add secret**

### 步驟四：取得 LINE Notify Token

1. 前往 [LINE Notify](https://notify-bot.line.me/my/)，登入你的 LINE 帳號
2. 點選 **發行權杖 (Generate token)**
3. 填入權杖名稱（如 `TQQQ Bot`），選擇要推送的聊天室
4. 複製產生的 Token，貼入 GitHub Secrets

### 步驟五：驗證執行

1. 前往 Repository → **Actions** 頁籤
2. 選擇 **TQQQ Daily Sniper Bot**
3. 點選 **Run workflow** 手動觸發，確認 CSV 更新並收到 LINE 通知

## 排程

- 自動執行：每週一至週五 UTC 12:00（台灣時間晚上 8:00）
- 手動執行：在 GitHub Actions 頁面點選 `Run workflow`

## 環境變數

| 變數 | 必填 | 說明 |
|------|------|------|
| `LINE_TOKEN` | ✅ | LINE Notify 存取權杖 |
| `QQQ_CSV_PATH` | ❌ | QQQ CSV 路徑，預設為 `data/QQQ_1d.csv`，不存在時自動 fallback 到 yfinance |
