import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.services.sql_agent_service import run_sql_agent


QUESTIONS = [
    "資訊部有哪些員工？列出姓名、職稱、email。",
    "各部門費用總額是多少？依金額高到低排序。",
    "找出還沒核准且金額超過 3000 的費用。",
    "哪個廠商的發票總金額最高？",
]


def main():
    app = create_app()

    with app.app_context():
        for question in QUESTIONS:
            result = run_sql_agent(
                api_key="",
                question=question,
                model="gpt-4o",
                temperature=0.2,
            )
            print(f"QUESTION: {question}")
            print(f"SQL: {result['sql']}")
            print(f"ROWS: {result['row_count']}")
            print(result["answer"])
            print("-" * 60)


if __name__ == "__main__":
    main()
