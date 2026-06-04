from app.db import get_engine
from app.services.answer_synthesizer_service import synthesize_answer
from app.services.audit_service import combine_usage
from app.services.schema_introspection_service import format_schema_for_prompt, get_schema_summary
from app.services.sql_executor_service import SqlExecutionError, execute_select_sql
from app.services.sql_generator_service import generate_sql
from app.services.sql_validator_service import SqlValidationError, validate_select_sql


class SqlAgentError(RuntimeError):
    pass


def run_sql_agent(api_key, question, model, temperature=0.2):
    engine = get_engine()
    schema = get_schema_summary(engine)
    schema_description = format_schema_for_prompt(schema)

    generated = generate_sql(
        api_key=api_key,
        question=question,
        model=model,
        schema_description=schema_description,
    )

    try:
        validation = validate_select_sql(generated.sql)
    except SqlValidationError as exc:
        raise SqlAgentError(f"產生的 SQL 未通過安全檢查：{exc}") from exc

    try:
        query_result = execute_select_sql(engine, validation.sql)
    except SqlExecutionError as exc:
        raise SqlAgentError(str(exc)) from exc

    synthesized = synthesize_answer(
        api_key=api_key,
        question=question,
        sql=validation.sql,
        columns=query_result["columns"],
        rows=query_result["rows"],
        model=model,
        temperature=temperature,
    )

    return {
        "route": "DB Query",
        "answer": synthesized["answer"],
        "sql": validation.sql,
        "raw_sql": generated.sql,
        "generator_reason": generated.reason,
        "generator_source": generated.source,
        "validator_warnings": validation.warnings,
        "columns": query_result["columns"],
        "rows": query_result["rows"],
        "row_count": query_result["row_count"],
        "usage": combine_usage(generated.usage, synthesized.get("usage")),
        "generator_usage": generated.usage,
        "answer_usage": synthesized.get("usage"),
    }
