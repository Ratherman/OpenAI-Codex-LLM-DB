# OpenAI Codex 實戰：打造可串接資料庫的 AI Agent 系統

這份講義是給講師逐段貼給 Codex 的 Prompt 腳本，目標是在 6 小時左右，從空專案疊加出一個可以在學員筆電運作的系統：

- 前端：React + Vite，三欄式 LLM 聊天室介面。
- 後端：Python Flask API。
- 資料庫：Docker Desktop 啟動 MySQL 8。
- LLM：可串接 OpenAI API，支援聊天、Context Router、RAG、SQL Agent、圖片欄位辨識與資料寫入。
- 最終情境：公司內部 AI Agent，可以查員工、部門、費用、發票、廠商資料，也可以從圖片辨識發票欄位後寫入資料庫。

> 建議講法：每一段 Prompt 都是一次「許願」。貼完後讓 Codex 實作、啟動、測試，再由學員觀察系統能力變化。

## 課程時間配置

| 時間 | 主題 | 對應 Prompt |
|---|---|---|
| 00:00-00:20 | 說明最終作品與檢查環境 | 1 |
| 00:20-01:00 | React + Flask 專案骨架 | 2-3 |
| 01:00-01:45 | Docker MySQL、資料表、種子資料 | 4-5 |
| 01:45-02:30 | 聊天室 UI、前後端串接、OpenAI API | 6-7 |
| 02:30-03:10 | 對話記憶、聊天紀錄存 DB | 8 |
| 03:10-03:50 | Context Router 與 Human-in-the-loop | 9 |
| 03:50-04:35 | 動態 SQL Agent 查詢資料庫 | 10 |
| 04:35-05:10 | 受控寫入資料庫與操作確認 | 11 |
| 05:10-05:35 | RAG 知識庫與資料庫整合 | 12 |
| 05:35-06:00 | 圖片 Skill、稽核紀錄、UIUX、總驗收 | 13-15 |

## 系統最終 Demo 題目

可以讓學員測試這些願望：

- 「幫我查資訊部有哪些員工，依職稱排序。」
- 「今年五月各部門費用總額是多少？請用表格回答。」
- 「找出超過 5000 元但還沒核准的費用。」
- 「新增一筆台北高鐵出差費用，員工是 Alice Wang，金額 1490 元，日期是 2026-05-22。」
- 「我上傳一張發票圖片，請幫我辨識統編、日期、品項、金額，確認後寫進資料庫。」
- 「VPN 連不上要怎麼辦？請引用公司 MIS SOP。」

---

## Prompt 1：請 Codex 先盤點環境與規劃專案

目標：不要急著寫程式，先讓 Codex 確認 Node、Python、Docker 是否可用，並建立清楚的專案規劃。

```text
Codex，我正在上「OpenAI Codex 實戰：打造可串接資料庫的 AI Agent 系統」課程。

我希望你先幫我檢查目前電腦環境，不要先大改檔案。請你完成：

1. 檢查目前資料夾內容。
2. 檢查 Node.js / npm 是否可用。
3. 檢查 Python 版本是否可用，優先支援 Python 3.10+
   目前已經有建立一個虛擬環境稱作是 Codex_Demo，他的 Python 環境是 python==3.11.15
4. 檢查 Docker 是否可用。（這個需要打開 Docker Desktop）
5. 檢查目前是否已經有 docker-compose.yml 或其他專案檔案。
6. 依照我的課程目標，提出你建議的專案結構。

我希望最後專案大概長這樣：

- frontend/：React + Vite 前端
- backend/：Python Flask API
- backend/app/：後端主要程式
- backend/scripts/：資料庫初始化、seed、embedding 等腳本
- backend/data/：QA 或範例資料
- docker-compose.yml：MySQL 8 資料庫
- README.md：如何啟動整個系統

這個系統的最終功能是：

- React 聊天室 UI
- Flask 後端 API
- Docker MySQL 資料庫，與員工和財務有些關聯
- OpenAI API 聊天
- Context Router 判斷一般聊天 / 查資料庫 / RAG / 圖片辨識
- SQL Agent 可以安全查詢資料庫
- 圖片辨識結果可以在使用者確認後寫入資料庫

請你先回報環境檢查結果與實作計畫，暫時不要開始建立大量檔案。
```

驗收重點：

- 學員知道自己缺 Node、Python 或 Docker 的哪一段。
- Codex 產出專案結構計畫。
- 還沒有進入不可逆的大量實作。

---

## Prompt 2：建立 React + Flask 最小可啟動專案

目標：建立前後端骨架，能在本機同時啟動。

```text
Codex，我現在要進入第 2 階段：建立最小可啟動的前後端專案。

請你直接幫我實作以下內容：

1. 建立 frontend/，使用 React + Vite。
2. 建立 backend/，使用 Flask。
3. 後端先提供：
   - GET /api/health
   - 回傳 JSON，例如 {"status": "ok", "service": "backend"}
4. 前端首頁先顯示：
   - 課程標題：「DB Agent Chat」
   - 後端連線狀態
   - 一個重新檢查後端狀態的按鈕
5. 加入 backend/requirements.txt。
6. 加入 .gitignore，至少排除：
   - .env
   - node_modules/
   - __pycache__/
   - .venv/
   - backend/uploads/
7. 在 README.md 寫清楚：
   - 如何安裝前端套件
   - 如何安裝後端套件
   - 如何啟動 Flask
   - 如何啟動 React

請你完成後實際執行必要的安裝或測試指令，確認前後端基本可用。如果需要開兩個 terminal，請在 README 寫清楚。
```

驗收重點：

- `frontend` 可以 `npm run dev`。
- `backend` 可以啟動 Flask。
- 前端能打到 `/api/health`。

---

## Prompt 3：打造三欄式聊天介面，先做 Echo Bot

目標：沿用上一堂 React LLM 聊天室模式，但目前先不串 LLM。

```text
Codex，我現在要進入第 3 階段：先把聊天 UI 做出來，但還不要串 OpenAI API。

請你改造 React 前端成三欄式介面：

左側 Sidebar：
- 可以新增聊天室。
- 顯示聊天室列表。
- 每個聊天室可以重新命名、刪除。
- 可以收合到左側，只留下展開按鈕。
- 左下角有 Light / Dark Mode 切換。

中間 Chat Area：
- 顯示使用者與系統訊息。
- 使用者訊息靠右。
- 系統訊息靠左。
- 下方有輸入框。
- Enter 送出，Shift+Enter 換行。
- 先加入上傳圖片按鈕，但這一階段可以先 disabled，顯示「圖片功能尚未啟用」。

右側 Control Panel：
- 可以收合到右側。
- 先放以下設定，但暫時不一定要真的串功能：
  - 模型選擇
  - Temperature 0 到 1
  - System Prompt
  - Memory 輪數 1 到 10
  - Enable Context Router
  - Enable DB Query
  - Enable RAG
  - Enable Image Skill
  - Enable Audit Log

互動行為：
- 使用者送出文字後，系統先回覆：
  「我收到你的訊息了：{使用者訊息}。下一階段會串接後端與 LLM。」
- 請把 UI 拆成合理的 React components。
- 請注意桌機與手機 RWD，手機版可以改成上方聊天列表按鈕、主聊天區、右側設定抽屜。
- 請不要做 landing page，第一畫面就是可操作的聊天工具。

完成後請啟動前端確認畫面沒有錯誤。
```

驗收重點：

- 學員看到「類 ChatGPT UI」。
- 可以送訊息並得到 echo 回覆。
- 左右欄可以收合。

---

## Prompt 4：加入 Docker MySQL 與資料庫連線設定

目標：使用事前環境準備的 MySQL 設定，讓後端能連 DB。

```text
請你更新 backend：

1. 使用 SQLAlchemy 連線 MySQL。
2. 使用 PyMySQL driver。
3. 使用 python-dotenv 讀取 .env。
4. 建立 .env.example，包含：
   - DATABASE_URL=mysql+pymysql://codex_user:codex_pass@127.0.0.1:3306/codex_demo
   - OPENAI_API_KEY=請填入你的 key

5. 新增 GET /api/db/health：
   - 成功時回傳資料庫版本與連線狀態。
   - 失敗時回傳清楚的錯誤訊息。
6. 前端右側或頂部要能顯示 DB 連線狀態。
7. README 補上：
   - docker compose up -d
   - docker compose ps
   - docker compose logs db
   - 如何重啟後端。

8. 讓回覆可以串接前端指定的語言模型
```

驗收重點：

- MySQL container 啟動。
- `/api/db/health` 可查到 DB 狀態。
- 前端顯示 DB connected / failed。

---

## Prompt 5：建立資料表與公司營運種子資料

目標：有真資料可以讓 Agent 查詢與寫入。

```text
Codex，我現在要進入第 5 階段：建立公司營運資料表與 seed data。

請你設計一個適合課堂 Demo 的 MySQL schema，至少包含：

1. departments
   - id
   - name
   - manager_name

2. employees
   - id
   - employee_code
   - name
   - department_id
   - title
   - email
   - location
   - hire_date

3. vendors
   - id
   - name
   - tax_id
   - contact_email

4. expense_reports
   - id
   - employee_id
   - vendor_id nullable
   - expense_date
   - category
   - amount
   - currency
   - status
   - description

5. invoices
   - id
   - vendor_id nullable
   - invoice_number
   - invoice_date
   - buyer_tax_id
   - seller_tax_id
   - total_amount
   - raw_text
   - source_image_path nullable
   - created_at

6. chat_rooms
7. chat_messages
8. audit_logs

請你完成：

- SQLAlchemy models。
- 初始化資料庫的 script，例如 backend/scripts/init_db.py。
- 匯入 seed data 的 script，例如 backend/scripts/seed_db.py。
- 至少建立：
  - 4 個部門
  - 12 位員工
  - 8 個廠商
  - 30 筆費用資料
  - 5 筆發票資料
- 新增 API：
  - GET /api/db/tables
  - GET /api/db/summary
  - GET /api/employees
  - GET /api/expenses
  - GET /api/invoices
- 前端右側 Control Panel 或資料分頁顯示資料庫摘要，例如員工數、費用總額、發票數。
- README 補上初始化與 seed 指令。

請你執行 init 與 seed，確認 API 可以讀到資料。

並且告訴我，如何在 docker 當中看到目前的資料
```

驗收重點：

- DB 內真的有資料。
- 前端可看到資料筆數摘要。
- 後續 SQL Agent 有足夠資料可查。

---

## Prompt 6：前後端聊天 API 串接，訊息存進資料庫

目標：從前端 echo 改成真正呼叫後端，並保存聊天紀錄。

```text
Codex，我現在要進入第 6 階段：讓聊天訊息透過後端 API，並存入資料庫。

目前前端是自己做 Echo Bot。請你改成：

後端新增：

- POST /api/chat/rooms：建立聊天室。
- GET /api/chat/rooms：取得聊天室列表。
- PATCH /api/chat/rooms/:id：修改聊天室名稱。
- DELETE /api/chat/rooms/:id：刪除聊天室與訊息。
- GET /api/chat/rooms/:id/messages：取得聊天室訊息。
- POST /api/chat/rooms/:id/messages：送出使用者訊息。

這一階段還不要串 OpenAI API，後端先回覆：
「後端已收到你的訊息：{message}。下一階段會由 LLM 回覆。」

資料庫要求：

- chat_rooms 要保存 title、created_at、updated_at。
- chat_messages 要保存 room_id、role、content、metadata_json、created_at。
- 使用者訊息與 assistant 回覆都要寫進 DB。

前端要求：

- 聊天室列表從 DB API 取得，不再只存在 React state。
- 重整頁面後聊天室與訊息仍存在。
- 新增、改名、刪除聊天室都要真的打 API。
- API loading / error 要有基本 UI。

完成後請測試：

1. 新增聊天室。
2. 送出訊息。
3. 重新整理頁面。
4. 確認訊息還在。
```

驗收重點：

- 聊天紀錄已經 DB-backed。
- 重整不會消失。

---

## Prompt 7：串接 OpenAI API 與右側模型設定

目標：正式讓 LLM 回覆，並保留可 Debug 的 API Key 狀態。

```text
Codex，我現在要進入第 7 階段：串接 OpenAI API。

請你幫我完成：

1. 後端從 .env 讀取 OPENAI_API_KEY 和 OPENAI_MODEL。
2. 加入 OpenAI Python SDK 到 requirements.txt。
3. 新增 GET /api/llm/health：
   - 檢查 OPENAI_API_KEY 是否存在。
   - 不要回傳完整 key。
   - 只回傳遮罩後的 key，例如 sk-...abcd。
   - 如果 key 不存在或 API 呼叫失敗，要回傳可理解的錯誤。
4. 修改 POST /api/chat/rooms/:id/messages：
   - 用 OpenAI API 產生 assistant 回覆。
   - 使用右側設定傳來的 model、temperature、systemPrompt。
   - temperature UI 限制在 0 到 1。
   - LLM 回覆要寫回 chat_messages。
5. 前端右側 Control Panel：
   - 模型可輸入或選擇。
   - temperature slider 0 到 1。
   - system prompt textarea。
   - 設定改變後下一次送出要生效。
6. 前端要能顯示 LLM health：
   - API Key 存在與否。
   - 目前讀到的遮罩 key。
   - 錯誤原因。
7. LLM 回覆如果包含 Markdown，前端要用 Markdown renderer 正常顯示，不要直接露出很多 ** 或 ### 造成難讀。

安全要求：

- 不要把任何真實 API Key 寫進程式碼或 README。
- .env 必須被 .gitignore 排除。
- .env.example 只能放 placeholder。

完成後請啟動後端與前端測試一次真實對話。如果沒有 OPENAI_API_KEY，請保留清楚錯誤提示，不要讓整個畫面壞掉。
```

驗收重點：

- 能用 LLM 真實回覆。
- API Key 讀取來源清楚。
- Markdown 正常渲染。

---

## Prompt 8：加入多輪記憶，並從資料庫讀取歷史訊息

目標：對話記憶不只存在前端，而是從 DB 訊息紀錄組裝。

```text
Codex，我現在要進入第 8 階段：加入多輪對話記憶。

請你讓右側 Memory 輪數設定真的生效：

- 範圍 1 到 10。
- 一輪代表 user + assistant 各一則訊息。
- 每次送出新訊息時，後端根據 room_id 從 chat_messages 讀取最近 N 輪。
- 組裝給 LLM 的 messages 應包含：
  - system prompt
  - 最近 N 輪歷史訊息
  - 最新 user message

請你注意：

1. 不要把整個聊天室所有訊息都塞給 LLM。
2. 不要把 metadata_json 當成 role message 亂塞進去。
3. 如果有非 user / assistant / system 的內部資料，請放在 system 或 developer-style context 文字中，不要使用 API 不支援的 role。
4. 前端要顯示目前 Memory 輪數。
5. 聊天室上方可以顯示「目前記憶：N 輪」。
6. README 補充 Memory 輪數的意義。

請你完成後用一個測試流程驗證：

- 第一輪：我叫做小明。
- 第二輪：我喜歡喝拿鐵。
- 第三輪：問「我喜歡喝什麼？」
- Memory 設成 1 與 3 時，觀察回覆差異。
```

驗收重點：

- 多輪記憶可調。
- 記憶來源是 DB。
- 不會誤用 unsupported role。

---

## Prompt 9：建立 Context Router 與人機確認流程

目標：讓每次回覆前先判斷要走哪一種能力。

```text
Codex，我現在要進入第 9 階段：建立 Context Router。

我希望每次使用者送出訊息後，如果 Enable Context Router 有開啟，後端先請 LLM 判斷這次任務要走哪一條路：

1. general_chat：一般聊天。
2. db_query：查詢資料庫，例如查員工、部門、費用、發票、廠商。
3. db_write：新增或修改資料庫資料，例如新增費用、寫入發票。
4. rag：查公司 SOP 或 MIS 常見問題。
5. image_skill：圖片辨識，例如發票、收據、文件截圖。

請你實作：

- 後端新增 router service。
- 使用 Pydantic model 驗證 router 輸出，欄位至少包含：
  - route
  - confidence
  - reason
  - required_capability
  - suggested_followup_question nullable
- 如果 LLM 輸出不是合法 JSON，要有 fallback，不要讓系統壞掉。
- 前端 Chat Area 在真正回覆前顯示 Router 判斷結果。
- 前端提供 Human-in-the-loop：
  - 顯示五種 route 按鈕。
  - AI 判斷的 route 亮起。
  - 使用者可改選。
  - 有「確認執行」按鈕。
- 右側加入 Auto Route toggle：
  - 開啟時，系統自動接受 router 判斷。
  - 關閉時，需要使用者確認。
- 如果某功能 toggle 沒開，例如 Enable DB Query 沒開，但 route 是 db_query，assistant 要回覆：「DB Query 尚未啟用，請先在右側開啟。」

這一階段先不用真的完成 db_query / db_write / rag / image_skill 的完整能力。沒有實作的 route 可以回覆「此能力將在下一階段啟用」。

請你加上測試案例，讓我可以輸入：

- 「請問今天心情如何？」應走 general_chat。
- 「資訊部有哪些員工？」應走 db_query。
- 「新增一筆餐費 320 元」應走 db_write。
- 「VPN 連不上怎麼辦？」應走 rag。
- 「這張發票幫我辨識」應走 image_skill。
```

驗收重點：

- Router 結果可見。
- 使用者可改 route。
- 功能沒開時會被擋下。

---

## Prompt 10：實作安全的動態 SQL Agent 查詢

目標：讓 Agent 可以查資料庫，但先只允許 SELECT。

```text
Codex，我現在要進入第 10 階段：實作安全的動態 SQL Agent。

當 Context Router 判斷 route 是 db_query，且右側 Enable DB Query 有開啟時，系統要能把自然語言轉成 SQL，查詢 MySQL，並用 LLM 整理回答。

請你設計安全機制：

1. 只允許 SELECT 查詢。
2. 禁止 INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE / CREATE。
3. SQL 必須加上 LIMIT，預設最多 50 筆。
4. 後端執行 SQL 前要用程式檢查，不要只靠 prompt。
5. 不允許多語句 SQL。
6. 錯誤時回傳友善訊息，不要把完整 stack trace 顯示給前端。

請你實作：

- schema introspection service：讓 LLM 知道有哪些 table、欄位、關聯。
- sql_generator service：把使用者問題轉成 SQL。
- sql_validator service：檢查 SQL 安全性。
- sql_executor service：執行 SQL。
- answer_synthesizer service：把查詢結果整理成繁體中文回答。

前端顯示：

- 本次使用 route：DB Query。
- 產生的 SQL，可收合。
- 查詢結果表格，可收合。
- LLM 整理後回答。

請你加入幾個可測試問題：

- 「資訊部有哪些員工？列出姓名、職稱、email。」
- 「各部門費用總額是多少？依金額高到低排序。」
- 「找出還沒核准且金額超過 3000 的費用。」
- 「哪個廠商的發票總金額最高？」

完成後請實際測試至少一個問題。
```

驗收重點：

- 自然語言可以查 DB。
- 前端可看到 SQL 與結果。
- 危險 SQL 會被擋。

---

## Prompt 11：實作受控 DB Write，不讓 LLM 直接亂改資料庫

目標：新增資料必須走白名單工具與使用者確認。

```text
Codex，我現在要進入第 11 階段：實作受控 DB Write。

這一階段要讓使用者可以用自然語言新增資料，但不能讓 LLM 直接產生任意 INSERT / UPDATE SQL 去改資料庫。

請你實作白名單工具：

1. create_expense_report
   - employee_name 或 employee_code
   - vendor_name nullable
   - expense_date
   - category
   - amount
   - currency 預設 TWD
   - description
   - status 預設 pending

2. create_invoice
   - vendor_name nullable
   - invoice_number
   - invoice_date
   - buyer_tax_id
   - seller_tax_id
   - total_amount
   - raw_text nullable
   - source_image_path nullable

流程要求：

- route 是 db_write 時，後端先抽取結構化欄位。
- 使用 Pydantic 驗證欄位。
- 如果必要欄位不足，assistant 要追問缺少的欄位。
- 欄位足夠時，不要立刻寫 DB。
- 前端先顯示「待確認寫入」卡片。
- 使用者按「確認寫入」後，才呼叫後端真正新增。
- 使用者可取消。
- 寫入成功後，在聊天訊息中顯示新增的資料 ID。
- audit_logs 要記錄這次寫入操作。

請你加入測試語句：

- 「幫 Alice Wang 新增一筆 2026-05-22 的高鐵費用 1490 元，廠商是台灣高鐵，類別交通，說明是台北到台中出差。」
- 「新增一張發票，號碼 AB12345678，日期 2026-05-20，賣方統編 12345678，買方統編 87654321，金額 3150。」

請你完成前後端流程，並實際用一筆費用資料測試。
```

驗收重點：

- 新增 DB 資料需要二次確認。
- LLM 只抽欄位，不直接改資料庫。
- audit log 有記錄。

---

## Prompt 12：把 RAG 知識庫放進資料庫，支援 REF 引用

目標：RAG 不只讀檔案，而是可和 DB 整合。

```text
Codex，我現在要進入第 12 階段：實作 RAG 知識庫，並把知識資料存在 MySQL。

RAG 用來處理公司 MIS / 行政 SOP 問題，例如：

- 忘記密碼
- VPN 無法連線
- Gmail 無法寄信
- 筆電黑畫面
- 印表機無法列印
- 發票報銷流程
- 出差費用核銷規則

請你完成：

1. 新增資料表 knowledge_chunks：
   - id
   - title
   - category
   - content
   - source
   - embedding_json
   - created_at
2. 建立 backend/data/qa_knowledge.json，至少 20 筆繁體中文 SOP。
3. 建立 backend/scripts/seed_knowledge.py：
   - 讀 qa_knowledge.json。
   - 呼叫 OpenAI embedding model 產生向量。
   - 把 embedding 以 JSON 存到 MySQL。
4. 實作 rag service：
   - 對 user query 產生 embedding。
   - 從 MySQL 讀取 knowledge_chunks。
   - 用 cosine similarity 找 top-k。
   - 預設 top_k = 3。
   - 把 chunks 提供給 LLM 整理回答。
5. 右側 Control Panel：
   - Enable RAG toggle。
   - Top-K slider，1 到 5。
6. 前端回覆：
   - 顯示 route：RAG。
   - 回答下方顯示 REF，可收合。
   - REF 格式使用 [1] [2] [3]，包含 title、source、相似度。

請注意：

- 如果沒有 OPENAI_API_KEY 或 embedding 失敗，要有清楚錯誤。
- 如果 knowledge_chunks 沒資料，要提示先執行 seed_knowledge.py。
- Router 的 prompt 也要知道 SOP / MIS / 行政流程問題應該走 rag。

請你完成後測試：

- 「VPN 連不上或密碼過期怎麼辦？」
- 「發票要怎麼報銷？」
```

驗收重點：

- 知識資料在 DB。
- RAG 回答有 REF。
- Top-K 可調。

---

## Prompt 13：實作圖片 Skill，辨識發票後寫入資料庫

目標：把圖片上傳、LLM 視覺辨識、確認寫入 DB 串起來。

```text
Codex，我現在要進入第 13 階段：實作 Image Skill，讓發票圖片可以辨識並寫入資料庫。

請你啟用前端上傳圖片功能：

前端要求：

- 使用者可以在聊天輸入區上傳圖片。
- 圖片縮圖顯示在聊天訊息中。
- 點縮圖可以開啟預覽 modal。
- 圖片與文字一起送到後端。
- 只有 Enable Image Skill 開啟時，才允許走 image_skill route。

後端要求：

- 新增 uploads 目錄保存圖片。
- 新增 POST /api/uploads/image。
- 接受 jpg / jpeg / png / webp。
- 限制檔案大小，例如 10MB。
- route 是 image_skill 時，把圖片交給 OpenAI vision-capable model 辨識。
- 請建立一個 backend/app/skills/invoice_extraction/SKILL.md，內容描述：
  - 這個 skill 用來辨識三聯式發票或收據。
  - 要抽取 invoice_number、invoice_date、buyer_tax_id、seller_tax_id、vendor_name、items、total_amount、raw_text。
  - 不確定的欄位要標記 null，不要亂猜。
- LLM 輸出要用 Pydantic 驗證。
- 辨識完成後，不要直接寫入 invoices。
- 前端先顯示「辨識結果待確認」卡片。
- 使用者按「確認寫入」後，才呼叫 create_invoice 寫入 DB。
- 寫入成功後顯示 invoice id。
- audit_logs 記錄圖片辨識與寫入。

請你也加入錯誤處理：

- 沒有圖片但選了 image_skill，要提示請上傳圖片。
- 圖片太大要提示。
- LLM 無法辨識時，要回傳可以理解的訊息。

完成後請用任一張本機圖片測試上傳流程。如果沒有真發票圖，也可以先測試「圖片上傳、預覽、後端保存、錯誤提示」都正常。
```

驗收重點：

- 圖片可上傳與預覽。
- 發票欄位可抽取。
- 寫入 DB 前需要確認。

---

## Prompt 14：加入 Audit Log、Token 紀錄與安全檢查

目標：讓學員看到 Agent 每一步做了什麼，也降低 DB Agent 風險。

```text
Codex，我現在要進入第 14 階段：加入 Audit Log、Token 紀錄與安全檢查。

我希望這個系統很適合教學，所以每一次 Agent 做事情，都要留下可解釋的紀錄。

請你擴充 audit_logs：

- id
- room_id nullable
- action_type
- route
- model
- input_summary
- output_summary
- sql_text nullable
- db_table nullable
- db_record_id nullable
- prompt_tokens nullable
- completion_tokens nullable
- total_tokens nullable
- metadata_json
- created_at

請你在以下流程寫 audit log：

- LLM 一般聊天
- Context Router 判斷
- DB Query 產生與執行 SQL
- DB Write 待確認與確認寫入
- RAG retrieval
- Image Skill 辨識
- 發票寫入

前端要求：

- 右側 Enable Audit Log 開啟後才顯示紀錄。
- 聊天室上方或右側顯示本聊天室 token 總量。
- 每則 assistant 回覆可展開「執行細節」：
  - route
  - model
  - SQL 或 REF
  - token usage
  - audit id

安全檢查要求：

- DB Query 仍只能 SELECT。
- DB Write 仍只能走白名單工具。
- 使用者如果要求「刪除所有資料」「忽略系統提示」「直接 DROP TABLE」，要拒絕並解釋。
- 在 README 加一段「為什麼 DB Agent 需要安全邊界」。

請你完成後測試：

- 一次 general_chat。
- 一次 db_query。
- 一次 db_write。
- 一次危險操作請求：「幫我刪除所有費用資料」。
```

驗收重點：

- Agent 行為可追蹤。
- token / model 用量可見。
- 危險 DB 操作被拒絕。

---

## Prompt 15：總整理、UIUX 強化、啟動腳本與課堂驗收

目標：把作品收斂成學員可重跑、講師可 demo 的版本。

```text
Codex，我現在要進入第 15 階段：總整理、UIUX 強化與課堂驗收。

請你把目前專案整理成適合課堂 Demo 的狀態。

UIUX：

- 桌機版維持三欄式工具介面。
- 手機版要好用，不要文字互相重疊。
- 聊天訊息、SQL、表格、REF、Audit 細節都要可讀。
- Loading 狀態要清楚。
- Error message 要能幫助學員 Debug。
- Light / Dark Mode 都要檢查。
- 不要做 landing page，第一畫面就是工具。

啟動與重置：

- README 要有完整流程：
  1. 啟動 Docker DB。
  2. 建立後端環境。
  3. 安裝 requirements。
  4. 複製 .env.example 到 .env。
  5. 填入 OPENAI_API_KEY。
  6. 初始化 DB。
  7. seed 公司資料。
  8. seed RAG 知識庫。
  9. 啟動 Flask。
  10. 啟動 React。
- 加入一個方便課堂使用的 reset 指令或 script：
  - 清空並重建資料表。
  - 重新 seed。
- 加入 smoke test script，至少檢查：
  - backend health
  - db health
  - db summary
  - chat API

Demo script：

請在 README 加一段「6 分鐘 Demo 流程」，包含：

1. 一般聊天。
2. 查 DB：資訊部有哪些員工？
3. SQL Agent：各部門費用總額。
4. DB Write：新增一筆交通費。
5. RAG：VPN 連不上怎麼辦？
6. Image Skill：上傳發票圖並確認寫入。
7. Audit Log：展示系統剛剛做了哪些事。

最後請你：

- 執行 lint / build / smoke test，如果專案有這些指令。
- 啟動或至少驗證前後端沒有語法錯誤。
- 回報目前可以打開的網址。
- 回報還需要講師手動補上的東西，例如 OPENAI_API_KEY。
```

驗收重點：

- README 足以讓學員照做。
- 老師可以用固定 Demo 題目展示。
- 系統從「聊天室」長成「可串 DB 的 AI Agent」。

---

## 備用 Debug Prompt

如果課堂中 Codex 做到一半出錯，可以插入下面這段：

```text
Codex，我現在遇到錯誤。請你先不要新增功能，改成 Debug 模式。

請你依序完成：

1. 重現錯誤。
2. 找出是前端、後端、DB、Docker、OpenAI API、或 .env 設定問題。
3. 只修最小必要範圍。
4. 修完後執行原本失敗的測試。
5. 在 README troubleshooting 補上一行這個錯誤的原因與解法。

以下是錯誤訊息：

請貼上錯誤訊息。
```