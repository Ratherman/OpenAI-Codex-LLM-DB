import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.router_service import route_message


CASES = [
    ("請問今天心情如何？", "general_chat"),
    ("資訊部有哪些員工？", "db_query"),
    ("新增一筆餐費 320 元", "db_write"),
    ("VPN 連不上怎麼辦？", "rag"),
    ("這張發票幫我辨識", "image_skill"),
]


def main():
    failures = []

    for message, expected_route in CASES:
        decision = route_message(api_key="", message=message, model="gpt-4o")
        passed = decision.route == expected_route
        mark = "PASS" if passed else "FAIL"
        print(f"{mark} | {message} | expected={expected_route} | actual={decision.route}")

        if not passed:
            failures.append((message, expected_route, decision.route))

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
