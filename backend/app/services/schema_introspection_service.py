from sqlalchemy import inspect

ALLOWED_QUERY_TABLES = (
    "departments",
    "employees",
    "vendors",
    "expense_reports",
    "invoices",
)

BUSINESS_ALIASES = {
    "資訊部": "Engineering",
    "工程部": "Engineering",
    "研發部": "Engineering",
    "財務部": "Finance",
    "業務部": "Sales",
    "銷售部": "Sales",
    "營運部": "Operations",
}


def get_schema_summary(engine):
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    tables = []
    relationships = []

    for table_name in ALLOWED_QUERY_TABLES:
        if table_name not in existing_tables:
            continue

        columns = []
        for column in inspector.get_columns(table_name):
            columns.append(
                {
                    "name": column["name"],
                    "type": str(column["type"]),
                    "nullable": bool(column.get("nullable", True)),
                    "primary_key": bool(column.get("primary_key", False)),
                }
            )

        tables.append({"name": table_name, "columns": columns})

        for foreign_key in inspector.get_foreign_keys(table_name):
            constrained = foreign_key.get("constrained_columns") or []
            referred = foreign_key.get("referred_columns") or []
            referred_table = foreign_key.get("referred_table")
            if referred_table not in ALLOWED_QUERY_TABLES:
                continue
            for local_column, remote_column in zip(constrained, referred):
                relationships.append(
                    {
                        "from": f"{table_name}.{local_column}",
                        "to": f"{referred_table}.{remote_column}",
                    }
                )

    return {
        "tables": tables,
        "relationships": relationships,
        "aliases": BUSINESS_ALIASES,
    }


def format_schema_for_prompt(schema):
    lines = ["Only these business tables may be queried:"]

    for table in schema["tables"]:
        lines.append(f"- {table['name']}")
        for column in table["columns"]:
            pk = " primary_key" if column["primary_key"] else ""
            nullable = " nullable" if column["nullable"] else " not_null"
            lines.append(f"  - {column['name']}: {column['type']}{pk}{nullable}")

    lines.append("Relationships:")
    for relationship in schema["relationships"]:
        lines.append(f"- {relationship['from']} -> {relationship['to']}")

    lines.append("Business aliases:")
    for chinese_name, seeded_name in schema["aliases"].items():
        lines.append(f"- {chinese_name} = {seeded_name}")

    return "\n".join(lines)
