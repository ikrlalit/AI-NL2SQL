# seed_memory.py
import asyncio
import uuid
from vanna.core.tool import ToolContext
from vanna.core.user.models import User
from vanna_setup import build_memory

# ── Schema DDL ────────────────────────────────────────────────────────────────
# Teaches the agent the exact table and column names so it never hallucinates
# tables like "transactions" or "payments".
SCHEMA_DDL = [
    """CREATE TABLE patients (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name      TEXT NOT NULL,
        last_name       TEXT NOT NULL,
        email           TEXT,
        phone           TEXT,
        city            TEXT,
        gender          TEXT,
        registered_date TEXT
    )""",
    """CREATE TABLE doctors (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT NOT NULL,
        specialization TEXT,
        department     TEXT
    )""",
    """CREATE TABLE appointments (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id       INTEGER NOT NULL,
        doctor_id        INTEGER NOT NULL,
        appointment_date TEXT,
        status           TEXT,   -- 'Scheduled', 'Completed', 'Cancelled', 'No-Show'
        FOREIGN KEY (patient_id) REFERENCES patients(id),
        FOREIGN KEY (doctor_id)  REFERENCES doctors(id)
    )""",
    """CREATE TABLE treatments (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_id   INTEGER NOT NULL,
        name             TEXT,
        cost             REAL,
        duration_minutes INTEGER,
        FOREIGN KEY (appointment_id) REFERENCES appointments(id)
    )""",
    """CREATE TABLE invoices (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id   INTEGER NOT NULL,
        invoice_date TEXT,
        total_amount REAL,   -- total billed amount (use this for revenue / spending)
        paid_amount  REAL,
        status       TEXT,   -- 'Paid', 'Pending', 'Overdue'
        FOREIGN KEY (patient_id) REFERENCES patients(id)
    )""",
]

# ── Q&A pairs ─────────────────────────────────────────────────────────────────
QA_PAIRS = [
    # ── Patients ──────────────────────────────────────────────────────────────
    ("How many patients do we have?",
     "SELECT COUNT(*) AS total_patients FROM patients"),

    ("List all patients in Mumbai",
     "SELECT first_name, last_name, phone, email FROM patients WHERE city = 'Mumbai'"),

    ("How many female patients do we have?",
     "SELECT COUNT(*) AS female_patients FROM patients WHERE gender = 'F'"),

    ("Which city has the most patients?",
     "SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1"),

    ("List patients who visited more than 3 times",
     "SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count FROM patients p JOIN appointments a ON a.patient_id = p.id GROUP BY p.id HAVING visit_count > 3 ORDER BY visit_count DESC"),

    ("Show patient registration trend by month",
     "SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients FROM patients GROUP BY month ORDER BY month"),

    # ── Doctors ───────────────────────────────────────────────────────────────
    ("List all doctors and their specializations",
     "SELECT name, specialization, department FROM doctors ORDER BY specialization"),

    ("Which doctor has the most appointments?",
     "SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON a.doctor_id = d.id GROUP BY d.id ORDER BY appointment_count DESC LIMIT 1"),

    ("Show average treatment duration by doctor",
     "SELECT d.name, ROUND(AVG(t.duration_minutes), 2) AS avg_duration FROM doctors d JOIN appointments a ON a.doctor_id = d.id JOIN treatments t ON t.appointment_id = a.id GROUP BY d.id ORDER BY avg_duration DESC"),

    # ── Appointments ──────────────────────────────────────────────────────────
    ("Show me appointments for last month",
     "SELECT a.id, p.first_name, p.last_name, d.name AS doctor, a.appointment_date, a.status FROM appointments a JOIN patients p ON a.patient_id = p.id JOIN doctors d ON a.doctor_id = d.id WHERE strftime('%Y-%m', a.appointment_date) = strftime('%Y-%m', date('now', '-1 month')) ORDER BY a.appointment_date"),

    ("How many cancelled appointments were there last quarter?",
     "SELECT COUNT(*) AS cancelled_count FROM appointments WHERE status = 'Cancelled' AND appointment_date >= date('now', '-3 months')"),

    ("Show monthly appointment count for the past 6 months",
     "SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS appointment_count FROM appointments WHERE appointment_date >= date('now', '-6 months') GROUP BY month ORDER BY month"),

    ("What percentage of appointments are no-shows?",
     "SELECT ROUND(COUNT(CASE WHEN status = 'No-Show' THEN 1 END) * 100.0 / COUNT(*), 2) AS no_show_percentage FROM appointments"),

    ("Show the busiest day of the week for appointments",
     "SELECT CASE strftime('%w', appointment_date) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' WHEN '6' THEN 'Saturday' END AS day_name, COUNT(*) AS appointment_count FROM appointments GROUP BY strftime('%w', appointment_date) ORDER BY appointment_count DESC LIMIT 1"),

    # ── Revenue / Invoices ────────────────────────────────────────────────────
    ("What is the total revenue?",
     "SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices"),

    ("Show revenue by doctor",
     "SELECT d.name, ROUND(SUM(i.total_amount), 2) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.name ORDER BY total_revenue DESC"),

    ("Show revenue trend by month",
     "SELECT strftime('%Y-%m', invoice_date) AS month, ROUND(SUM(total_amount), 2) AS monthly_revenue FROM invoices GROUP BY month ORDER BY month"),

    ("Compare revenue between departments",
     "SELECT d.department, ROUND(SUM(i.total_amount), 2) AS total_revenue, COUNT(DISTINCT i.id) AS invoice_count FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.department ORDER BY total_revenue DESC"),

    ("Show unpaid invoices",
     "SELECT p.first_name, p.last_name, i.invoice_date, i.total_amount, i.paid_amount, i.status FROM invoices i JOIN patients p ON i.patient_id = p.id WHERE i.status IN ('Pending', 'Overdue') ORDER BY i.status, i.invoice_date"),

    ("List patients with overdue invoices",
     "SELECT DISTINCT p.first_name, p.last_name, p.email, p.city FROM patients p JOIN invoices i ON i.patient_id = p.id WHERE i.status = 'Overdue' ORDER BY p.last_name"),

    # ── Spending (invoices.total_amount) ──────────────────────────────────────
    # These pairs explicitly map "spending / spend / cost" to the invoices table
    # so the agent never hallucinates a "transactions" table.
    ("Show me the top 5 patients by total spending",
     "SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount), 2) AS total_spending FROM patients p JOIN invoices i ON i.patient_id = p.id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5"),

    ("Top 5 patients by spending",
     "SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount), 2) AS total_spending FROM patients p JOIN invoices i ON i.patient_id = p.id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5"),

    ("Which patients spent the most?",
     "SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount), 2) AS total_spending FROM patients p JOIN invoices i ON i.patient_id = p.id GROUP BY p.id ORDER BY total_spending DESC LIMIT 10"),

    ("What is the average amount billed per patient?",
     "SELECT ROUND(AVG(total_per_patient), 2) AS avg_spending FROM (SELECT patient_id, SUM(total_amount) AS total_per_patient FROM invoices GROUP BY patient_id)"),

    # ── Treatments ────────────────────────────────────────────────────────────
    ("Average treatment cost by specialization",
     "SELECT d.specialization, ROUND(AVG(t.cost), 2) AS avg_cost FROM treatments t JOIN appointments a ON t.appointment_id = a.id JOIN doctors d ON a.doctor_id = d.id GROUP BY d.specialization ORDER BY avg_cost DESC"),
]


async def seed_async():
    print("Building memory …")
    memory = build_memory()

    seed_user = User(id="seed", email="seed@clinic.local", group_memberships=["user"])
    context = ToolContext(
        user=seed_user,
        conversation_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
        agent_memory=memory,
    )

    # ── 1. Train DDL schema ───────────────────────────────────────────────────
    # Try known Vanna 2.0 method names in order of likelihood.
    ddl_method = None
    for candidate in ("add_ddl", "train_ddl", "add_documentation", "train"):
        if hasattr(memory, candidate) and callable(getattr(memory, candidate)):
            ddl_method = candidate
            break

    if ddl_method:
        print(f"Training schema DDL via memory.{ddl_method}() …")
        ok_ddl = 0
        for ddl in SCHEMA_DDL:
            try:
                result = getattr(memory, ddl_method)(ddl.strip())
                # Some methods return a coroutine
                if asyncio.iscoroutine(result):
                    await result
                ok_ddl += 1
            except Exception as e:
                print(f"  ⚠ DDL training failed: {e}")
        print(f"  Schema trained — {ok_ddl}/{len(SCHEMA_DDL)} tables.\n")
    else:
        print("  ⚠ No DDL training method found on memory object — skipping.\n")

    # ── 2. Seed Q&A pairs ─────────────────────────────────────────────────────
    print(f"Seeding {len(QA_PAIRS)} Q&A pairs …\n")
    ok = 0
    for i, (question, sql) in enumerate(QA_PAIRS, 1):
        try:
            await memory.save_tool_usage(
                question=question,
                tool_name="run_sql",
                args={"sql": sql},
                context=context,
                success=True,
            )
            print(f"  [{i:02d}/{len(QA_PAIRS)}] ✓  {question}")
            ok += 1
        except Exception as e:
            print(f"  [{i:02d}/{len(QA_PAIRS)}] ✗  {question}\n       Error: {e}")

    print(f"\n✅ Done — {ok}/{len(QA_PAIRS)} pairs seeded.")
    return memory


def seed():
    return asyncio.run(seed_async())


if __name__ == "__main__":
    seed()