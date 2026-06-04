# RAG 知識庫新增 SOP

這份文件說明如何自行新增 RAG 題目，讓系統可以回答公司 MIS、行政、財務或內部流程相關問題。

## 目前資料來源

RAG 的主要知識來源是：

```text
backend/data/qa_knowledge.json
```

資料會透過下面的 script 產生 embedding，並寫入 MySQL 的 `knowledge_chunks` 資料表：

```text
backend/scripts/seed_knowledge.py
```

目前的 `seed_knowledge.py` 會先清空 `knowledge_chunks`，再把整份 `qa_knowledge.json` 重新寫入 MySQL。

因此請把 `qa_knowledge.json` 當作主要資料來源，不建議只手動修改 MySQL，否則下次重新 seed 時會被覆蓋。

## 新增一筆 RAG 題目

打開 `backend/data/qa_knowledge.json`，在 JSON 陣列最後新增一筆資料。

範例：

```json
{
  "title": "Slack 無法登入",
  "category": "MIS",
  "source": "MIS-SOP-022",
  "content": "如果 Slack 無法登入，請先確認公司帳號是否可正常登入 SSO。若 SSO 正常，請清除瀏覽器快取或改用桌面版重新登入。若仍失敗，請截圖錯誤訊息並提交 MIS 工單。"
}
```

欄位說明：

- `title`：這筆知識的標題，建議簡短明確。
- `category`：分類，例如 `MIS`、`行政`、`財務`。
- `source`：來源代碼，例如 `MIS-SOP-022`、`FIN-SOP-006`。
- `content`：實際會提供給 RAG 的知識內容，建議寫成可直接回答使用者的 SOP。

## 重新產生 embedding

新增或修改 `qa_knowledge.json` 後，需要重新執行 seed script：

```powershell
python backend/scripts/seed_knowledge.py
```

如果使用課程虛擬環境：

```powershell
C:\Users\USER\anaconda3\envs\Codex_Demo\python.exe backend/scripts/seed_knowledge.py
```

執行前請確認 `.env` 有設定：

```text
OPENAI_API_KEY=你的 OpenAI API Key
```

不要把真實 API Key 寫進 README 或任何會提交到 Git 的檔案。

## 確認資料是否寫入 MySQL

可以用 Docker 進入 MySQL 查詢目前筆數：

```powershell
docker compose exec db mysql -ucodex_user -pcodex_pass codex_demo -e "SELECT COUNT(*) FROM knowledge_chunks;"
```

也可以查看最近幾筆：

```powershell
docker compose exec db mysql -ucodex_user -pcodex_pass codex_demo -e "SELECT id, title, category, source FROM knowledge_chunks ORDER BY id DESC LIMIT 5;"
```

## 前端測試方式

1. 啟動後端 Flask。
2. 啟動前端 React。
3. 打開右側 Control Panel。
4. 開啟 `Enable RAG`。
5. 設定 `RAG Top-K`，預設可用 `3`。
6. 在聊天室輸入和新增 SOP 相關的問題。

範例：

```text
Slack 無法登入怎麼辦？
```

如果 RAG 正常運作，assistant 回覆下方會顯示 REF，例如：

```text
[1] Slack 無法登入 / MIS-SOP-022 / 0.72
```

## 撰寫建議

每筆 `content` 建議包含：

- 使用者可能會問的關鍵字。
- 明確處理步驟。
- 需要聯絡哪個單位，例如 MIS、行政或財務。
- 需要附上的資料，例如截圖、發票號碼、錯誤訊息。
- 何時需要升級處理。

較好的寫法：

```text
如果 VPN 無法連線，請先確認網路是否正常，再重新啟動 VPN client。若顯示密碼過期，請先到 SSO 變更密碼，等待 5 分鐘後再重新登入 VPN。若仍無法連線，請截圖錯誤訊息並提交 MIS 工單。
```

較不建議的寫法：

```text
VPN 壞掉請找 MIS。
```

原因是內容太短，RAG 找得到資料後也無法整理出有用的回答。

## 常見問題

### 新增資料後前端問不到怎麼辦？

請確認：

- `qa_knowledge.json` 是合法 JSON。
- 已重新執行 `seed_knowledge.py`。
- `.env` 有設定 `OPENAI_API_KEY`。
- 右側 `Enable RAG` 已開啟。
- 問題文字和 SOP 內容有足夠關聯。

### 可以只改 MySQL 嗎？

不建議。因為 `seed_knowledge.py` 會重新覆蓋 `knowledge_chunks`，手動新增到 MySQL 的資料下次 seed 可能會消失。

### Top-K 要設多少？

一般建議：

- `1`：只想看最相關的一筆。
- `3`：預設值，適合大多數 SOP 問答。
- `5`：問題比較模糊，想讓 LLM 參考更多資料。
