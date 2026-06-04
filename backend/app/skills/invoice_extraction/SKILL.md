# Invoice Extraction Skill

這個 skill 用來辨識三聯式發票、電子發票、收據或費用憑證圖片。

## 任務

從圖片中抽取可用於建立 `invoices` 資料表的結構化欄位：

- `invoice_number`：發票號碼或收據號碼。
- `invoice_date`：發票日期，格式必須是 `YYYY-MM-DD`。
- `buyer_tax_id`：買方統一編號。
- `seller_tax_id`：賣方統一編號。
- `vendor_name`：賣方或店家名稱。
- `items`：明細項目陣列，每筆可包含品名、數量、單價、金額。
- `total_amount`：總金額。
- `raw_text`：圖片中可讀到的原始文字摘要。

## 輸出規則

- 只輸出合法 JSON object，不要輸出 Markdown。
- 不確定的欄位必須標記為 `null`，不要猜測。
- 看不到買方統編或賣方統編時，請填 `null`。
- 看不到日期時，請填 `null`。
- 金額只能輸出數字，不要包含 `$`、`,` 或幣別文字。
- 如果圖片不是發票或收據，也要輸出 JSON，並在 `notes` 說明無法辨識的原因。

## JSON 格式

```json
{
  "invoice_number": null,
  "invoice_date": null,
  "buyer_tax_id": null,
  "seller_tax_id": null,
  "vendor_name": null,
  "items": [
    {
      "description": null,
      "quantity": null,
      "unit_price": null,
      "amount": null
    }
  ],
  "total_amount": null,
  "raw_text": null,
  "confidence": 0.0,
  "notes": []
}
```
