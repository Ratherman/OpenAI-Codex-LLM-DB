import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.db import get_session
from app.models import ChatMessage


def seed_pending_invoice_message(room_id):
    metadata = {
        "provider": "image_skill",
        "selected_route": "image_skill",
        "image_skill": {
            "route": "Image Skill",
            "status": "pending_confirmation",
            "image": {
                "filename": "png.png",
                "path": "uploads/png.png",
                "url": "http://127.0.0.1:5000/api/uploads/image/png.png",
                "content_type": "image/png",
                "size": 123,
            },
            "extraction": {
                "invoice_number": "ZZ12345678",
                "invoice_date": "2015-01-20",
                "buyer_tax_id": None,
                "seller_tax_id": "13574246",
                "vendor_name": "範例股份有限公司",
                "items": [],
                "total_amount": "10000",
                "raw_text": "測試發票",
                "confidence": 0.9,
                "notes": [],
            },
        },
        "db_write": {
            "status": "missing_fields",
            "tool": "create_invoice",
            "fields": {
                "vendor_name": "範例股份有限公司",
                "invoice_number": "ZZ12345678",
                "invoice_date": "2015-01-20",
                "buyer_tax_id": None,
                "seller_tax_id": "13574246",
                "total_amount": "10000",
                "raw_text": "測試發票",
                "source_image_path": "uploads/png.png",
            },
            "missing_fields": ["buyer_tax_id"],
            "message": "辨識完成，但缺少必要欄位，請補充後再寫入資料庫。",
            "origin": "image_skill",
            "image": {
                "filename": "png.png",
                "path": "uploads/png.png",
                "url": "http://127.0.0.1:5000/api/uploads/image/png.png",
                "content_type": "image/png",
                "size": 123,
            },
        },
    }
    session = get_session()
    try:
        session.add(
            ChatMessage(
                room_id=room_id,
                role="assistant",
                content="辨識完成，但缺少必要欄位，請補充後再寫入資料庫。",
                metadata_json=json.dumps(metadata, ensure_ascii=False),
            )
        )
        session.commit()
    finally:
        session.close()


def main():
    app = create_app()
    app.config["TESTING"] = True
    app.config["OPENAI_API_KEY"] = ""

    with app.test_client() as client:
        create_response = client.post("/api/chat/rooms", json={"title": "Image Skill Follow-up Test"})
        assert create_response.status_code == 201, create_response.get_data(as_text=True)
        room_id = create_response.get_json()["room"]["id"]

        seed_pending_invoice_message(room_id)

        route_response = client.post(
            f"/api/chat/rooms/{room_id}/route",
            json={"message": "buyer tax id 是 62192453", "model": "gpt-4o"},
        )
        assert route_response.status_code == 200, route_response.get_data(as_text=True)
        route_payload = route_response.get_json()
        assert route_payload["router"]["route"] == "image_skill", route_payload

        message_response = client.post(
            f"/api/chat/rooms/{room_id}/messages",
            json={
                "message": "buyer tax id 是 62192453",
                "model": "gpt-4o",
                "temperature": 0.2,
                "enableContextRouter": True,
                "enableImageSkill": True,
                "autoRoute": True,
                "confirmedRoute": "image_skill",
            },
        )
        assert message_response.status_code == 201, message_response.get_data(as_text=True)
        payload = message_response.get_json()
        assistant = payload["messages"][-1]
        db_write = assistant["metadata"]["db_write"]

        assert payload["selected_route"] == "image_skill", payload
        assert db_write["status"] == "pending_confirmation", db_write
        assert db_write["fields"]["buyer_tax_id"] == "62192453", db_write

        print("Image Skill follow-up test passed.")
        print(f"room_id={room_id}")


if __name__ == "__main__":
    main()
