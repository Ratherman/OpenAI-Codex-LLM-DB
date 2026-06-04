from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


class SqlExecutionError(RuntimeError):
    pass


def to_jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def execute_select_sql(engine, sql):
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql))
            columns = list(result.keys())
            rows = [
                {column: to_jsonable(row._mapping[column]) for column in columns}
                for row in result.fetchall()
            ]
    except SQLAlchemyError as exc:
        raise SqlExecutionError("SQL 查詢執行失敗，請確認問題是否符合目前資料表。") from exc

    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
    }
