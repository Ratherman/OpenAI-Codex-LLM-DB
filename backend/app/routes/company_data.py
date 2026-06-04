from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_session
from app.models import (
    AuditLog,
    ChatMessage,
    ChatRoom,
    Department,
    Employee,
    ExpenseReport,
    Invoice,
    Vendor,
)

company_data_bp = Blueprint("company_data", __name__)

TABLE_MODELS = [
    Department,
    Employee,
    Vendor,
    ExpenseReport,
    Invoice,
    ChatRoom,
    ChatMessage,
    AuditLog,
]


def money(value):
    if value is None:
        return "0.00"
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return f"{Decimal(value):.2f}"


def query_limit(default=100, maximum=500):
    try:
        limit = int(request.args.get("limit", default))
    except (TypeError, ValueError):
        limit = default

    return max(1, min(limit, maximum))


def serialize_employee(employee):
    return {
        "id": employee.id,
        "employee_code": employee.employee_code,
        "name": employee.name,
        "department_id": employee.department_id,
        "department": employee.department.name,
        "title": employee.title,
        "email": employee.email,
        "location": employee.location,
        "hire_date": employee.hire_date.isoformat(),
    }


def serialize_expense(expense):
    return {
        "id": expense.id,
        "employee_id": expense.employee_id,
        "employee_name": expense.employee.name,
        "vendor_id": expense.vendor_id,
        "vendor_name": expense.vendor.name if expense.vendor else None,
        "expense_date": expense.expense_date.isoformat(),
        "category": expense.category,
        "amount": money(expense.amount),
        "currency": expense.currency,
        "status": expense.status,
        "description": expense.description,
    }


def serialize_invoice(invoice):
    return {
        "id": invoice.id,
        "vendor_id": invoice.vendor_id,
        "vendor_name": invoice.vendor.name if invoice.vendor else None,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat(),
        "buyer_tax_id": invoice.buyer_tax_id,
        "seller_tax_id": invoice.seller_tax_id,
        "total_amount": money(invoice.total_amount),
        "raw_text": invoice.raw_text,
        "source_image_path": invoice.source_image_path,
        "created_at": invoice.created_at.isoformat(),
    }


@company_data_bp.get("/api/db/tables")
def list_tables():
    session = get_session()
    try:
        tables = []
        for model in TABLE_MODELS:
            row_count = session.execute(select(func.count()).select_from(model)).scalar_one()
            tables.append({"name": model.__tablename__, "row_count": row_count})

        return jsonify({"status": "ok", "tables": tables})
    except SQLAlchemyError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@company_data_bp.get("/api/db/summary")
def db_summary():
    session = get_session()
    try:
        expense_total = session.execute(select(func.coalesce(func.sum(ExpenseReport.amount), 0))).scalar_one()
        invoice_total = session.execute(select(func.coalesce(func.sum(Invoice.total_amount), 0))).scalar_one()

        status_rows = session.execute(
            select(ExpenseReport.status, func.count()).group_by(ExpenseReport.status)
        ).all()

        summary = {
            "department_count": session.execute(select(func.count()).select_from(Department)).scalar_one(),
            "employee_count": session.execute(select(func.count()).select_from(Employee)).scalar_one(),
            "vendor_count": session.execute(select(func.count()).select_from(Vendor)).scalar_one(),
            "expense_count": session.execute(select(func.count()).select_from(ExpenseReport)).scalar_one(),
            "expense_total": money(expense_total),
            "invoice_count": session.execute(select(func.count()).select_from(Invoice)).scalar_one(),
            "invoice_total": money(invoice_total),
            "chat_room_count": session.execute(select(func.count()).select_from(ChatRoom)).scalar_one(),
            "audit_log_count": session.execute(select(func.count()).select_from(AuditLog)).scalar_one(),
            "expense_status_counts": {status: count for status, count in status_rows},
        }

        return jsonify({"status": "ok", "summary": summary})
    except SQLAlchemyError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@company_data_bp.get("/api/employees")
def list_employees():
    session = get_session()
    try:
        employees = session.execute(
            select(Employee).join(Employee.department).order_by(Employee.employee_code).limit(query_limit())
        ).scalars()
        return jsonify({"status": "ok", "employees": [serialize_employee(employee) for employee in employees]})
    except SQLAlchemyError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@company_data_bp.get("/api/expenses")
def list_expenses():
    session = get_session()
    try:
        expenses = session.execute(
            select(ExpenseReport)
            .join(ExpenseReport.employee)
            .outerjoin(ExpenseReport.vendor)
            .order_by(ExpenseReport.expense_date.desc(), ExpenseReport.id.desc())
            .limit(query_limit())
        ).scalars()
        return jsonify({"status": "ok", "expenses": [serialize_expense(expense) for expense in expenses]})
    except SQLAlchemyError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()


@company_data_bp.get("/api/invoices")
def list_invoices():
    session = get_session()
    try:
        invoices = session.execute(
            select(Invoice)
            .outerjoin(Invoice.vendor)
            .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
            .limit(query_limit())
        ).scalars()
        return jsonify({"status": "ok", "invoices": [serialize_invoice(invoice) for invoice in invoices]})
    except SQLAlchemyError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        session.close()
