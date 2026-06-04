import sys
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
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


def seed_departments(session):
    departments = [
        Department(name="Sales", manager_name="Alice Chen"),
        Department(name="Engineering", manager_name="Brian Lin"),
        Department(name="Finance", manager_name="Cathy Wang"),
        Department(name="Operations", manager_name="David Wu"),
    ]
    session.add_all(departments)
    session.flush()
    return {department.name: department for department in departments}


def seed_employees(session, departments):
    employee_rows = [
        ("E001", "Amy Chen", "Sales", "Sales Manager", "amy.chen@example.com", "Taipei", "2020-03-16"),
        ("E002", "Ben Lin", "Sales", "Account Executive", "ben.lin@example.com", "Taichung", "2021-06-01"),
        ("E003", "Carol Wu", "Sales", "Customer Success Specialist", "carol.wu@example.com", "Taipei", "2022-09-19"),
        ("E004", "Daniel Huang", "Engineering", "Engineering Manager", "daniel.huang@example.com", "Taipei", "2019-11-04"),
        ("E005", "Eva Tsai", "Engineering", "Backend Engineer", "eva.tsai@example.com", "Hsinchu", "2021-02-22"),
        ("E006", "Frank Liu", "Engineering", "Frontend Engineer", "frank.liu@example.com", "Taipei", "2023-01-09"),
        ("E007", "Grace Wang", "Finance", "Finance Manager", "grace.wang@example.com", "Taipei", "2018-05-07"),
        ("E008", "Henry Chang", "Finance", "Accountant", "henry.chang@example.com", "Kaohsiung", "2020-08-24"),
        ("E009", "Ivy Lee", "Finance", "FP&A Analyst", "ivy.lee@example.com", "Taipei", "2022-04-11"),
        ("E010", "Jackie Ho", "Operations", "Operations Manager", "jackie.ho@example.com", "Taoyuan", "2019-07-15"),
        ("E011", "Kevin Yu", "Operations", "Procurement Specialist", "kevin.yu@example.com", "Taipei", "2021-12-06"),
        ("E012", "Lily Hsu", "Operations", "Office Administrator", "lily.hsu@example.com", "Tainan", "2023-03-20"),
    ]
    employees = [
        Employee(
            employee_code=code,
            name=name,
            department_id=departments[department_name].id,
            title=title,
            email=email,
            location=location,
            hire_date=date.fromisoformat(hire_date),
        )
        for code, name, department_name, title, email, location, hire_date in employee_rows
    ]
    session.add_all(employees)
    session.flush()
    return {employee.employee_code: employee for employee in employees}


def seed_vendors(session):
    vendor_rows = [
        ("Acme Office Supplies", "24536806", "billing@acme-office.example.com"),
        ("CloudCore Software", "53124689", "ar@cloudcore.example.com"),
        ("Metro Travel Service", "80357122", "invoice@metrotravel.example.com"),
        ("Northwind Logistics", "28945173", "finance@northwind.example.com"),
        ("Bright Catering", "77654310", "orders@brightcatering.example.com"),
        ("Pixel Design Studio", "39012845", "hello@pixelstudio.example.com"),
        ("Taipei Training Center", "61890237", "admin@training.example.com"),
        ("Green Energy Utilities", "92734561", "service@greenenergy.example.com"),
    ]
    vendors = [
        Vendor(name=name, tax_id=tax_id, contact_email=email)
        for name, tax_id, email in vendor_rows
    ]
    session.add_all(vendors)
    session.flush()
    return {vendor.name: vendor for vendor in vendors}


def seed_expense_reports(session, employees, vendors):
    employee_codes = list(employees.keys())
    vendor_names = list(vendors.keys())
    categories = ["Travel", "Meals", "Software", "Office", "Training", "Logistics"]
    statuses = ["submitted", "approved", "reimbursed", "rejected"]
    amounts = [
        "1280.00",
        "2450.00",
        "3999.00",
        "860.00",
        "5200.00",
        "1775.00",
        "960.00",
        "3150.00",
        "4800.00",
        "720.00",
        "6400.00",
        "2300.00",
        "1120.00",
        "2890.00",
        "3550.00",
        "910.00",
        "7600.00",
        "1420.00",
        "2680.00",
        "980.00",
        "4100.00",
        "530.00",
        "2200.00",
        "6900.00",
        "1840.00",
        "3300.00",
        "2550.00",
        "1200.00",
        "4580.00",
        "810.00",
    ]

    expense_reports = []
    for index in range(30):
        employee = employees[employee_codes[index % len(employee_codes)]]
        vendor = vendors[vendor_names[index % len(vendor_names)]]
        expense_reports.append(
            ExpenseReport(
                employee_id=employee.id,
                vendor_id=vendor.id if index % 7 != 0 else None,
                expense_date=date(2026, 1 + (index % 6), 3 + (index % 24)),
                category=categories[index % len(categories)],
                amount=Decimal(amounts[index]),
                currency="TWD",
                status=statuses[index % len(statuses)],
                description=f"{categories[index % len(categories)]} expense for demo transaction {index + 1}",
            )
        )

    session.add_all(expense_reports)


def seed_invoices(session, vendors):
    invoice_rows = [
        ("INV-2026-0001", "Acme Office Supplies", "2026-01-15", "12345678", "24536806", "15230.00", "Acme Office Supplies invoice for office chairs and paper.", None),
        ("INV-2026-0002", "CloudCore Software", "2026-02-03", "12345678", "53124689", "86400.00", "Annual SaaS subscription renewal for engineering team.", None),
        ("INV-2026-0003", "Metro Travel Service", "2026-02-19", "12345678", "80357122", "32880.00", "Business travel package for customer visits.", "uploads/invoices/metro-2026-0003.jpg"),
        ("INV-2026-0004", "Bright Catering", "2026-03-08", "12345678", "77654310", "18600.00", "Catering invoice for company workshop.", None),
        ("INV-2026-0005", None, "2026-03-28", "12345678", "00000000", "4200.00", "Invoice captured from image, vendor pending manual confirmation.", "uploads/invoices/pending-2026-0005.jpg"),
    ]
    invoices = []
    for number, vendor_name, invoice_date, buyer_tax_id, seller_tax_id, total, raw_text, image_path in invoice_rows:
        invoices.append(
            Invoice(
                vendor_id=vendors[vendor_name].id if vendor_name else None,
                invoice_number=number,
                invoice_date=date.fromisoformat(invoice_date),
                buyer_tax_id=buyer_tax_id,
                seller_tax_id=seller_tax_id,
                total_amount=Decimal(total),
                raw_text=raw_text,
                source_image_path=image_path,
            )
        )
    session.add_all(invoices)


def seed_chat_and_audit(session):
    room = ChatRoom(title="Demo DB Agent Room")
    session.add(room)
    session.flush()
    session.add_all(
        [
            ChatMessage(
                room_id=room.id,
                role="user",
                content="Show me employee expense summary.",
                metadata_json=json.dumps({"model": "gpt-4o", "source": "seed"}),
            ),
            ChatMessage(
                room_id=room.id,
                role="assistant",
                content="I can query seeded expense data after SQL Agent is enabled.",
                metadata_json=json.dumps({"model": "gpt-4o", "provider": "seed"}),
            ),
            AuditLog(actor="system", action="init_db", target_type="database", target_id=None, details="Created classroom demo tables."),
            AuditLog(actor="system", action="seed_db", target_type="database", target_id=None, details="Seeded company operations demo data."),
        ]
    )


def clear_demo_data(session):
    for model in [
        AuditLog,
        ChatMessage,
        ChatRoom,
        Invoice,
        ExpenseReport,
        Vendor,
        Employee,
        Department,
    ]:
        session.execute(delete(model))


def main():
    app = create_app()

    with app.app_context():
        session = get_session()
        try:
            clear_demo_data(session)
            departments = seed_departments(session)
            employees = seed_employees(session, departments)
            vendors = seed_vendors(session)
            seed_expense_reports(session, employees, vendors)
            seed_invoices(session, vendors)
            seed_chat_and_audit(session)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    print("Seeded demo data:")
    print("- departments: 4")
    print("- employees: 12")
    print("- vendors: 8")
    print("- expense_reports: 30")
    print("- invoices: 5")


if __name__ == "__main__":
    main()
