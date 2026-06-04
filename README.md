# DB Agent Chat

「OpenAI Codex 實戰：打造可串接資料庫的 AI Agent 系統」課程專案。

目前功能：

- React + Vite 三欄式聊天 UI
- Flask 後端 API
- SQLAlchemy + PyMySQL 連線 MySQL
- `GET /api/health`
- `GET /api/db/health`
- `POST /api/chat`
- 前端可顯示 DB 連線狀態
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
│  │  ├─ __init__.py
│  │  └─ main.py
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
