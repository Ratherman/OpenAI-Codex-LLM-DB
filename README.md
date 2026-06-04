# DB Agent Chat

「OpenAI Codex 實戰：打造可串接資料庫的 AI Agent 系統」第 2 階段最小可啟動前後端專案。

目前功能：

- React + Vite 前端首頁
- Flask 後端 API
- `GET /api/health`
- 前端可檢查後端連線狀態

## 專案結構

```text
.
├─ frontend/
│  ├─ src/
│  │  ├─ App.jsx
│  │  ├─ App.css
│  │  └─ main.jsx
│  ├─ index.html
│  ├─ package.json
│  └─ vite.config.js
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py
│  │  └─ routes/
│  │     └─ health.py
│  └─ requirements.txt
├─ docker-compose.yml
└─ README.md
```

## 安裝後端套件

建議使用已建立好的 `Codex_Demo` conda 環境：

```powershell
conda activate Codex_Demo
cd backend
python -m pip install -r requirements.txt
```

## 啟動 Flask 後端

開啟第一個 terminal：

```powershell
conda activate Codex_Demo
cd backend
python -m flask --app app.main run --debug --host 127.0.0.1 --port 5000
```

後端健康檢查：

```powershell
curl http://127.0.0.1:5000/api/health
```

預期回傳：

```json
{"service":"backend","status":"ok"}
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

如果後端不是跑在 `http://127.0.0.1:5000`，可以在啟動前端前設定：

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:5000"
npm run dev
```

## Docker MySQL

目前 `docker-compose.yml` 已包含 MySQL 8。需要資料庫時可從專案根目錄執行：

```powershell
docker compose up -d
```
