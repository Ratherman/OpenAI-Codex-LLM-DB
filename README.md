# DB Agent Chat

「OpenAI Codex 實戰：打造可串接資料庫的 AI Agent 系統」課程專案。

目前功能：

- React + Vite 三欄式聊天 UI
- Flask 後端 API
- SQLAlchemy + PyMySQL 連線 MySQL
- `GET /api/health`
- `GET /api/db/health`
- `GET /api/db/tables`
- `GET /api/db/summary`
- `GET /api/employees`
- `GET /api/expenses`
- `GET /api/invoices`
- `POST /api/chat`
- 前端可顯示 DB 連線狀態
- 前端右側 Control Panel 可顯示資料庫摘要
- 前端選到的模型會送到後端，後端可依 `.env` 的 `OPENAI_API_KEY` 決定 mock 或呼叫 OpenAI

## 專案結構

```text
.
├─ frontend/
│  ├─ src/
│  │  ├─ components/
│  │  ├─ App.jsx
│  │  ├─ App.css
│  │  └─ main.jsx
│  ├─ index.html
│  ├─ package.json
│  └─ vite.config.js
├─ backend/
│  ├─ app/
│  │  ├─ routes/
│  │  ├─ services/
│  │  ├─ config.py
│  │  ├─ db.py
│  │  ├─ models.py
│  │  ├─ __init__.py
│  │  └─ main.py
│  ├─ scripts/
│  │  ├─ init_db.py
│  │  └─ seed_db.py
│  └─ requirements.txt
├─ .env.example
├─ docker-compose.yml
└─ README.md
```

## 環境變數

先複製範例檔：

```powershell
Copy-Item .env.example .env
```

`.env.example` 內容：

```env
DATABASE_URL=mysql+pymysql://codex_user:codex_pass@127.0.0.1:3306/codex_demo
OPENAI_API_KEY=請填入你的 key
```

如果暫時沒有 OpenAI API Key，可以先留空或保留範例文字。後端會先用 mock 回覆。

## 啟動 MySQL

從專案根目錄執行：

```powershell
docker compose up -d
```

檢查容器狀態：

```powershell
docker compose ps
```

查看 MySQL log：

```powershell
docker compose logs db
```

## 初始化與 Seed 資料庫

先確認 MySQL 已啟動：

```powershell
docker compose up -d
docker compose ps
```

建立資料表：

```powershell
conda activate Codex_Demo
python backend/scripts/init_db.py
```

匯入課堂 demo seed data：

```powershell
conda activate Codex_Demo
python backend/scripts/seed_db.py
```

`seed_db.py` 會重建固定 demo data，方便課堂重跑：

- 4 個部門
- 12 位員工
- 8 個廠商
- 30 筆費用資料
- 5 筆發票資料
- 少量 chat/audit 範例紀錄

資料 API：

```powershell
curl http://127.0.0.1:5000/api/db/tables
curl http://127.0.0.1:5000/api/db/summary
curl http://127.0.0.1:5000/api/employees
curl http://127.0.0.1:5000/api/expenses
curl http://127.0.0.1:5000/api/invoices
```

## 在 Docker 裡查看目前資料

進入 MySQL client：

```powershell
docker exec -it codex_db mysql -ucodex_user -pcodex_pass codex_demo
```

進入後可以執行：

```sql
SHOW TABLES;
SELECT COUNT(*) AS employee_count FROM employees;
SELECT COUNT(*) AS expense_count FROM expense_reports;
SELECT SUM(amount) AS expense_total FROM expense_reports;
SELECT * FROM employees LIMIT 5;
SELECT * FROM invoices LIMIT 5;
```

也可以直接用一行指令查詢：

```powershell
docker exec -it codex_db mysql -ucodex_user -pcodex_pass codex_demo -e "SHOW TABLES; SELECT COUNT(*) AS employees FROM employees; SELECT SUM(amount) AS expense_total FROM expense_reports;"
```

## 安裝後端套件

建議使用已建立好的 `Codex_Demo` conda 環境：

```powershell
conda activate Codex_Demo
python -m pip install -r backend/requirements.txt
```

## 啟動 Flask 後端

開啟第一個 terminal：

```powershell
conda activate Codex_Demo
cd backend
python -m flask --app app.main run --debug --host 127.0.0.1 --port 5000
```

健康檢查：

```powershell
curl http://127.0.0.1:5000/api/health
curl http://127.0.0.1:5000/api/db/health
```

## 重啟後端

如果 Flask 是在前景 terminal 執行，先按 `Ctrl+C` 停止，再重新執行：

```powershell
cd backend
python -m flask --app app.main run --debug --host 127.0.0.1 --port 5000
```

如果忘記是哪個 terminal 跑在 `5000` port，可以查詢並停止：

```powershell
Get-NetTCPConnection -LocalPort 5000 -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess
Stop-Process -Id <OwningProcess>
```

## 安裝前端套件

開啟第二個 terminal：

```powershell
cd frontend
npm install
```

## 啟動 React 前端

同一個前端 terminal：

```powershell
npm run dev
```

前端預設網址：

```text
http://localhost:5173
```

如果後端不是跑在 `http://127.0.0.1:5000`，啟動前端前設定：

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:5000"
npm run dev
```

## Chat API

前端送出訊息時會呼叫：

```http
POST /api/chat
```

會帶入右側設定面板的：

- `model`
- `temperature`
- `systemPrompt`
- `memoryRounds`
- Context Router / DB Query / RAG / Image Skill / Audit Log 開關

如果 `.env` 有有效的 `OPENAI_API_KEY`，後端會使用前端指定的 `model` 呼叫 OpenAI。沒有 key 時會使用 mock 回覆，方便課程階段先驗證前後端串接。