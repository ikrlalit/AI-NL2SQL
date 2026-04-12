# seed_memory.py
import asyncio
import uuid
from vanna.core.tool import ToolContext
from vanna.core.user.models import User
from vanna_setup import build_memory

QA_PAIRS = [
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
    ("List all doctors and their specializations",
     "SELECT name, specialization, department FROM doctors ORDER BY specialization"),
    ("Which doctor has the most appointments?",
     "SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON a.doctor_id = d.id GROUP BY d.id ORDER BY appointment_count DESC LIMIT 1"),
    ("Show average treatment duration by doctor",
     "SELECT d.name, ROUND(AVG(t.duration_minutes), 2) AS avg_duration FROM doctors d JOIN appointments a ON a.doctor_id = d.id JOIN treatments t ON t.appointment_id = a.id GROUP BY d.id ORDER BY avg_duration DESC"),
    ("Show me appointments for last month",
     "SELECT a.id, p.first_name, p.last_name, d.name AS doctor, a.appointment_date, a.status FROM appointments a JOIN patients p ON a.patient_id = p.id JOIN doctors d ON a.doctor_id = d.id WHERE strftime('%Y-%m', a.appointment_date) = strftime('%Y-%m', date('now', '-1 month')) ORDER BY a.appointment_date"),
    ("How many cancelled appointments were there last quarter?",
     "SELECT COUNT(*) AS cancelled_count FROM appointments WHERE status = 'Cancelled' AND appointment_date >= date('now', '-3 months')"),
    ("Show monthly appointment count for the past 6 months",
     "SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS appointment_count FROM appointments WHERE appointment_date >= date('now', '-6 months') GROUP BY month ORDER BY month"),
    ("What is the total revenue?",
     "SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices"),
    ("Show revenue by doctor",
     "SELECT d.name, ROUND(SUM(i.total_amount), 2) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.name ORDER BY total_revenue DESC"),
    ("Show unpaid invoices",
     "SELECT p.first_name, p.last_name, i.invoice_date, i.total_amount, i.paid_amount, i.status FROM invoices i JOIN patients p ON i.patient_id = p.id WHERE i.status IN ('Pending', 'Overdue') ORDER BY i.status, i.invoice_date"),
    ("Show patient registration trend by month",
     "SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients FROM patients GROUP BY month ORDER BY month"),
]


async def seed_async():
    print("Building memory …")
    memory = build_memory()

    seed_user = User(id="seed", email="seed@clinic.local", group_memberships=["user"])

    # ToolContext requires all 4 fields
    context = ToolContext(
        user=seed_user,
        conversation_id=str(uuid.uuid4()),   # ← required
        request_id=str(uuid.uuid4()),         # ← required
        agent_memory=memory,                  # ← required
    )

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