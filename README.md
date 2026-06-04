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
- `GET /api/llm/health`
- `POST /api/uploads/image`
- `POST /api/chat/rooms`
- `GET /api/chat/rooms`
- `PATCH /api/chat/rooms/:id`
- `DELETE /api/chat/rooms/:id`
- `GET /api/chat/rooms/:id/messages`
- `POST /api/chat/rooms/:id/route`
- `POST /api/chat/rooms/:id/messages`
- `GET /api/chat/rooms/:id/audit-logs`
- `POST /api/chat/rooms/:id/db-write/confirm`
- `POST /api/chat/rooms/:id/db-write/cancel`
- `POST /api/chat`
- 前端可顯示 DB 連線狀態
- 前端右側 Control Panel 可顯示資料庫摘要
- 聊天室與訊息會寫入 MySQL，重新整理頁面後仍會保留
- 前端選到的模型會送到後端並寫入 `metadata_json`
- 第 7 階段已串接 OpenAI API；如果沒有 `OPENAI_API_KEY`，前端會顯示清楚錯誤
- 第 14 階段加入 Audit Log、token usage 與安全檢查

## Audit Log、Token 與安全邊界

第 14 階段會把 Agent 的重要行為寫入 `audit_logs`，方便課堂示範每一步為什麼發生、用了哪個 route、是否產生 SQL、用了多少 token。

目前會記錄：

- Context Router 判斷
- LLM 一般聊天
- DB Query 產生與執行 SQL
- DB Write 待確認與確認寫入
- RAG retrieval
- Image Skill 發票辨識
- 發票或費用寫入
- 危險操作拒絕

前端右側 `Enable Audit Log` 開啟時會顯示本聊天室最近的 audit logs。聊天室上方會顯示本聊天室累計 token 總量。每則 assistant 回覆也可以展開「執行細節」，查看 route、model、SQL 或 REF、token usage 與 audit id。

查詢本聊天室 audit logs：

```powershell
curl http://127.0.0.1:5000/api/chat/rooms/1/audit-logs
```

### 為什麼 DB Agent 需要安全邊界

DB Agent 會把自然語言轉成資料庫操作，因此不能只相信 prompt。這個 demo 使用多層安全邊界：

- DB Query 只能執行 `SELECT`，程式會拒絕 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`TRUNCATE`、`CREATE`。
- SQL 不允許多語句，必須有 `LIMIT`，預設最多 50 筆。
- DB Write 不讓 LLM 直接寫任意 SQL，只能走白名單工具 `create_expense_report` 與 `create_invoice`。
- 寫入資料庫前一定要由使用者在前端按「確認寫入」。
- 危險請求例如「刪除所有資料」、「忽略系統提示」、「直接 DROP TABLE」會被安全檢查拒絕並留下 audit log。

這些限制讓系統適合教學：學生可以看到 AI 的推理與工具結果，但資料庫仍有明確邊界。

## Image Skill 圖片辨識

第 13 階段加入 Image Skill，讓使用者可以在聊天室上傳發票、收據或文件截圖。

Image Skill 的多輪補欄位不是只靠一般聊天記憶。系統會在 `chat_messages.metadata_json`
保留上一張發票的 `image_skill` 與 `db_write` 狀態。若上一張發票仍是
`missing_fields` 或 `pending_confirmation`，使用者後續輸入例如
`buyer tax id 是 62192453`、`請幫我彙整剛剛的發票資訊`，會優先接續這張待確認發票，
而不是要求重新上傳圖片或改走 DB Query。

前端流程：

1. 右側 Control Panel 開啟 `Enable Image Skill`。
2. 在聊天輸入區按 `上傳圖片`。
3. 支援 `jpg`、`jpeg`、`png`、`webp`。
4. 單張圖片大小上限為 `10MB`。
5. 上傳成功後會在輸入區顯示縮圖。
6. 送出後，圖片縮圖會保存在聊天訊息中。
7. 點縮圖可以開啟圖片預覽 modal。

後端上傳 API：

```http
POST /api/uploads/image
```

表單欄位：

```text
image=<圖片檔案>
```

圖片會保存在：

```text
backend/uploads/
```

此資料夾已在 `.gitignore` 中排除，不會提交圖片檔。

Image Skill route 流程：

1. Context Router 判斷或使用者手動選擇 `image_skill`。
2. 若 `Enable Image Skill` 未開啟，assistant 會提示：`Image Skill 尚未啟用，請先在右側開啟。`
3. 若沒有上傳圖片但選了 `image_skill`，assistant 會提示：`請先上傳圖片，再使用 Image Skill 進行發票或收據辨識。`
4. 有圖片時，後端會把圖片交給 OpenAI vision-capable model 辨識。
5. 辨識輸出會用 Pydantic 驗證。
6. 系統不會直接寫入 `invoices`。
7. 前端會先顯示「辨識結果待確認」卡片。
8. 使用者按 `確認寫入` 後，才會呼叫白名單工具 `create_invoice` 寫入資料庫。
9. 寫入成功後，聊天訊息會顯示新增的 invoice id。
10. `audit_logs` 會記錄圖片辨識與確認寫入。

Invoice extraction skill 說明檔位於：

```text
backend/app/skills/invoice_extraction/SKILL.md
```

測試上傳 API：

```powershell
curl.exe -F "image=@C:\path\to\invoice.png;type=image/png" http://127.0.0.1:5000/api/uploads/image
```

測試 Image Skill 補欄位流程：

```powershell
conda activate Codex_Demo
python backend/scripts/test_image_skill_followup.py
```

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

如果暫時沒有 OpenAI API Key，可以先留空或保留範例文字。後端會回傳清楚的 LLM 未啟用提示，不會讓前端畫面壞掉。

安全提醒：

- 不要把真實 API Key 寫進 README、程式碼或 `.env.example`
- 真實 key 只放在本機 `.env`
- `.env` 已被 `.gitignore` 排除

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

## Chat Rooms API

第 6 階段開始，前端聊天室與訊息都改由後端 API + MySQL 保存。第 7 階段開始，送出訊息時會使用 OpenAI API 產生 assistant 回覆。

建立聊天室：

```powershell
curl -X POST http://127.0.0.1:5000/api/chat/rooms `
  -H "Content-Type: application/json" `
  -d "{\"title\":\"Demo Room\"}"
```

取得聊天室列表：

```powershell
curl http://127.0.0.1:5000/api/chat/rooms
```

修改聊天室名稱：

```powershell
curl -X PATCH http://127.0.0.1:5000/api/chat/rooms/1 `
  -H "Content-Type: application/json" `
  -d "{\"title\":\"Renamed Room\"}"
```

刪除聊天室與訊息：

```powershell
curl -X DELETE http://127.0.0.1:5000/api/chat/rooms/1
```

取得聊天室訊息：

```powershell
curl http://127.0.0.1:5000/api/chat/rooms/1/messages
```

送出使用者訊息：

```powershell
curl -X POST http://127.0.0.1:5000/api/chat/rooms/1/messages `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"hello\",\"model\":\"gpt-4o\",\"temperature\":0.3,\"memoryRounds\":3}"
```

後端會寫入：

- `user` 訊息
- `assistant` LLM 回覆，或在 API key 缺失 / API 呼叫失敗時寫入清楚錯誤訊息

如果沒有設定 `OPENAI_API_KEY`，assistant 會回覆類似：

```text
LLM 尚未啟用：OPENAI_API_KEY is not configured. Please set it in .env and restart the backend.
```

`chat_messages` 會保存：

- `room_id`
- `role`
- `content`
- `metadata_json`
- `created_at`

## Memory 輪數

右側 Control Panel 的 `Memory 輪數` 會控制每次送給 LLM 的最近對話歷史。

- 範圍：`1` 到 `10`
- 一輪代表一組 `user` + `assistant` 訊息
- 後端會根據 `room_id` 從 `chat_messages` 讀取最近 N 輪
- 組裝給 LLM 的內容包含：
  - `systemPrompt`
  - 最近 N 輪 `user` / `assistant` 歷史訊息
  - 最新的 user message
- 不會把整個聊天室所有訊息都送給 LLM
- 不會把 `metadata_json` 當成 role message 塞進 LLM

範例：如果 `memoryRounds` 是 `3`，後端最多會帶入最近 3 輪，也就是最多 6 則歷史訊息，再加上本次最新 user message。

## LLM Health API

檢查 OpenAI API key 是否存在，以及 API 是否可連線：

```powershell
curl http://127.0.0.1:5000/api/llm/health
```

成功時只會回傳遮罩後的 key，例如：

```json
{
  "status": "ok",
  "configured": true,
  "api_reachable": true,
  "key_masked": "sk-...abcd"
}
```

不會回傳完整 API Key。

## Legacy Chat API

前端送出訊息時會呼叫：

```http
POST /api/chat
```

舊版 API 仍保留作為相容入口，但目前前端已改用 `/api/chat/rooms/:id/messages`。

前端送出訊息到聊天室 API 時會帶入右側設定面板的：

- `model`
- `temperature`
- `systemPrompt`
- `memoryRounds`
- Context Router / DB Query / RAG / Image Skill / Audit Log 開關

`POST /api/chat/rooms/:id/messages` 會呼叫 OpenAI，並把 assistant 回覆寫回 `chat_messages`。

## Context Router

第 9 階段加入 Context Router。當右側 `Enable Context Router` 開啟時，前端會先呼叫：

```http
POST /api/chat/rooms/:id/route
```

Router 會回傳：

```json
{
  "route": "general_chat",
  "confidence": 0.82,
  "reason": "這是一般聊天，不需要查資料庫。",
  "required_capability": "general_chat",
  "suggested_followup_question": null
}
```

支援的 route：

- `general_chat`：一般聊天。
- `db_query`：查詢員工、部門、費用、發票、廠商等資料庫資料。
- `db_write`：新增或修改資料庫資料。
- `rag`：查公司 SOP 或 MIS 常見問題。
- `image_skill`：圖片辨識，例如發票、收據、文件截圖。

右側 `Auto Route` 關閉時，聊天區會顯示五種 route 按鈕，使用者可改選後按「確認執行」。`Auto Route` 開啟時，系統會自動接受 Router 判斷。

目前第 9 階段只完成路由判斷與 gate：

- `general_chat` 會繼續呼叫 OpenAI。
- `db_query` 若 `Enable DB Query` 關閉，會回覆：`DB Query 尚未啟用，請先在右側開啟。`
- `rag` 若 `Enable RAG` 關閉，會回覆：`RAG 尚未啟用，請先在右側開啟。`
- `image_skill` 若 `Enable Image Skill` 關閉，會回覆：`Image Skill 尚未啟用，請先在右側開啟。`
- 已啟用但尚未實作的能力會回覆：`此能力將在下一階段啟用。`

Router 使用 Pydantic 驗證 LLM 的 JSON 輸出；如果 OpenAI API key 不存在、API 呼叫失敗，或 LLM 輸出不是合法 JSON，後端會使用關鍵字 fallback，不會讓系統壞掉。

測試 Router fallback：

```powershell
conda activate Codex_Demo
python backend/scripts/test_context_router.py
```

課堂測試句：

- `請問今天心情如何？` 應走 `general_chat`
- `資訊部有哪些員工？` 應走 `db_query`
- `新增一筆餐費 320 元` 應走 `db_write`
- `VPN 連不上怎麼辦？` 應走 `rag`
- `這張發票幫我辨識` 應走 `image_skill`

## SQL Agent

第 10 階段加入安全的動態 SQL Agent。當 Context Router 判斷為 `db_query`，且右側 `Enable DB Query` 開啟時，後端會執行：

1. `schema_introspection_service`：讀取可查詢的業務資料表、欄位與關聯。
2. `sql_generator_service`：把自然語言問題轉成 MySQL `SELECT`。
3. `sql_validator_service`：在程式層檢查 SQL 安全性。
4. `sql_executor_service`：執行 SQL。
5. `answer_synthesizer_service`：把查詢結果整理成繁體中文回答。

安全限制：

- 只允許 `SELECT`。
- 禁止 `INSERT` / `UPDATE` / `DELETE` / `DROP` / `ALTER` / `TRUNCATE` / `CREATE` 等語法。
- 不允許多語句 SQL。
- 不允許 SQL comment。
- SQL 必須有 `LIMIT`，沒有時自動補 `LIMIT 50`，超過 50 會自動降到 50。
- 只允許查詢業務表：`departments`、`employees`、`vendors`、`expense_reports`、`invoices`。
- 不允許查詢 `chat_rooms`、`chat_messages`、`audit_logs` 或系統表。
- 錯誤時回傳友善訊息，不把完整 stack trace 顯示給前端。

前端 assistant 泡泡會顯示：

- 本次使用 route：`DB Query`
- 可收合的產生 SQL
- 可收合的查詢結果表格
- LLM 整理後的繁體中文回答

測試 SQL Agent fallback：

```powershell
conda activate Codex_Demo
python backend/scripts/test_sql_agent.py
```

可測試問題：

- `資訊部有哪些員工？列出姓名、職稱、email。`
- `各部門費用總額是多少？依金額高到低排序。`
- `找出還沒核准且金額超過 3000 的費用。`
- `哪個廠商的發票總金額最高？`

## 受控 DB Write

第 11 階段加入受控資料庫寫入。當 Context Router 判斷為 `db_write` 時，後端不允許 LLM 產生任意 `INSERT` / `UPDATE` SQL，而是只允許兩個白名單工具：

- `create_expense_report`
- `create_invoice`

流程：

1. 後端先從自然語言抽取結構化欄位。
2. 使用 Pydantic 驗證欄位。
3. 必要欄位不足時，assistant 會追問缺少欄位。
4. 欄位足夠時，assistant 只回傳「待確認寫入」卡片。
5. 使用者按「確認寫入」後，前端才呼叫確認 endpoint。
6. 後端重新驗證白名單工具 payload，使用 ORM 寫入資料庫。
7. 寫入成功後，聊天訊息會顯示新增資料 ID。
8. `audit_logs` 會記錄這次寫入操作。

確認 / 取消 endpoint：

```http
POST /api/chat/rooms/:id/db-write/confirm
POST /api/chat/rooms/:id/db-write/cancel
```

安全限制：

- LLM 只能抽取欄位，不能直接產生寫入 SQL。
- 後端只執行白名單工具。
- 寫入前會二次驗證 Pydantic schema。
- `create_expense_report` 必須能找到既有員工；廠商可為空或未關聯。
- `create_invoice` 可選擇性關聯既有廠商。

可測試語句：

- `幫 Alice Wang 新增一筆 2026-05-22 的高鐵費用 1490 元，廠商是台灣高鐵，類別交通，說明是台北到台中出差。`
- `新增一張發票，號碼 AB12345678，日期 2026-05-20，賣方統編 12345678，買方統編 87654321，金額 3150。`

注意：seed data 目前沒有 `Alice Wang` 這位員工，所以第一句會要求補充正確的 employee code 或員工姓名。若要測試成功寫入費用，可改用既有員工，例如：

```text
幫 E005 新增一筆 2026-05-22 的高鐵費用 1490 元，廠商是台灣高鐵，類別交通，說明是台北到台中出差。
```

## RAG 知識庫

第 12 階段加入 RAG 知識庫，資料存在 MySQL 的 `knowledge_chunks` 資料表：

- `id`
- `title`
- `category`
- `content`
- `source`
- `embedding_json`
- `created_at`

知識來源檔案：

```text
backend/data/qa_knowledge.json
```

初始化資料表：

```powershell
conda activate Codex_Demo
python backend/scripts/init_db.py
```

產生 embeddings 並寫入 MySQL：

```powershell
conda activate Codex_Demo
python backend/scripts/seed_knowledge.py
```

`seed_knowledge.py` 會使用 `text-embedding-3-small`。如果沒有設定 `OPENAI_API_KEY`，或 embedding API 呼叫失敗，script 會顯示錯誤並停止。

RAG 流程：

1. 使用者問題產生 embedding。
2. 從 MySQL 讀取 `knowledge_chunks`。
3. 使用 cosine similarity 找 top-k。
4. 預設 `top_k = 3`，右側 `RAG Top-K` 可設定 1 到 5。
5. 把 REF chunks 提供給 LLM 整理繁體中文回答。

前端顯示：

- 本次使用 route：`RAG`
- 回答下方顯示可收合 `REF`
- REF 使用 `[1] [2] [3]`，包含 title、source、similarity

如果 `knowledge_chunks` 沒資料，系統會提示先執行：

```powershell
python backend/scripts/seed_knowledge.py
```

可測試問題：

- `VPN 連不上或密碼過期怎麼辦？`
- `發票要怎麼報銷？`
