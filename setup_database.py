"""
setup_database.py
Clinic Management System — Schema creation + Dummy data insertion
Run: python setup_database.py
Output: clinic.db
"""

import sqlite3
import random
from datetime import datetime, timedelta, date

# ── Seeded for reproducibility ──────────────────────────────────────────────
random.seed(42)

DB_PATH = "clinic.db"

# ── Raw reference data ───────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarav", "Aditya", "Akash", "Amit", "Ananya", "Anjali", "Arjun", "Aryan",
    "Ayesha", "Bhavna", "Chandan", "Deepa", "Deepak", "Divya", "Farhan",
    "Gaurav", "Geeta", "Harsh", "Isha", "Jatin", "Kavita", "Kiran", "Kunal",
    "Lakshmi", "Manish", "Meera", "Mihir", "Mohan", "Mukesh", "Neeraj",
    "Neha", "Nikhil", "Nisha", "Pallavi", "Pooja", "Pradeep", "Priya",
    "Rahul", "Raj", "Rajan", "Rajesh", "Rakesh", "Ramesh", "Ravi", "Rekha",
    "Ritika", "Rohit", "Rohan", "Sachin", "Sanjay", "Sangeeta", "Sara",
    "Sarika", "Shikha", "Shiv", "Shruti", "Sneha", "Suresh", "Swati",
    "Tanvi", "Tarun", "Usha", "Varun", "Vikram", "Vikas", "Vishal",
    "Yamini", "Yash", "Zara", "Abhishek", "Alok", "Amrita", "Ankur",
    "Bharat", "Chhaya", "Dinesh", "Ekta", "Ganesh", "Harish", "Indira",
    "Jagdish", "Kalyani", "Lalit", "Madhu", "Nandita", "Om", "Pankaj",
    "Rashmi", "Sunita", "Trilok", "Uma", "Vandana", "Wasim", "Xavier",
]

LAST_NAMES = [
    "Agarwal", "Bose", "Chandra", "Chopra", "Das", "Desai", "Dubey",
    "Gandhi", "Ghosh", "Gupta", "Iyer", "Jain", "Joshi", "Kapoor",
    "Khan", "Kumar", "Malhotra", "Mehta", "Mishra", "Mukherjee",
    "Nair", "Pandey", "Patel", "Pillai", "Rao", "Reddy", "Saxena",
    "Shah", "Sharma", "Singh", "Sinha", "Srivastava", "Tiwari",
    "Tripathi", "Varma", "Verma", "Yadav", "Bhat", "Naik", "Patil",
]

CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
]

SPECIALIZATIONS = ["Dermatology", "Cardiology", "Orthopedics", "General", "Pediatrics"]

DEPARTMENTS = {
    "Dermatology": "Skin & Hair",
    "Cardiology": "Heart & Vascular",
    "Orthopedics": "Bone & Joint",
    "General": "General Medicine",
    "Pediatrics": "Child Health",
}

DOCTOR_NAMES = [
    ("Dr. Arun",       "Mehta"),
    ("Dr. Sunita",     "Rao"),
    ("Dr. Vikram",     "Singh"),
    ("Dr. Priya",      "Sharma"),
    ("Dr. Rajesh",     "Iyer"),
    ("Dr. Kavita",     "Patel"),
    ("Dr. Manish",     "Gupta"),
    ("Dr. Ananya",     "Joshi"),
    ("Dr. Sameer",     "Khan"),
    ("Dr. Deepa",      "Nair"),
    ("Dr. Rahul",      "Verma"),
    ("Dr. Sneha",      "Mishra"),
    ("Dr. Arjun",      "Bose"),
    ("Dr. Meena",      "Chopra"),
    ("Dr. Nikhil",     "Reddy"),
]

TREATMENT_NAMES = {
    "Dermatology":  ["Chemical Peel", "Acne Treatment", "Skin Biopsy", "Mole Removal",
                     "Laser Therapy", "Eczema Management", "Psoriasis Treatment"],
    "Cardiology":   ["ECG", "Echocardiography", "Stress Test", "Holter Monitor",
                     "Angiography", "Blood Pressure Management", "Lipid Profile Review"],
    "Orthopedics":  ["X-Ray Consultation", "Physiotherapy Session", "Joint Injection",
                     "Fracture Management", "Arthroscopy", "Bone Density Test"],
    "General":      ["General Checkup", "Blood Test Review", "Vaccination",
                     "Fever Consultation", "Nutrition Counseling", "Allergy Test"],
    "Pediatrics":   ["Child Vaccination", "Growth Assessment", "Developmental Screening",
                     "Ear Infection Treatment", "Nutritional Guidance", "Asthma Management"],
}

COST_RANGES = {
    "Dermatology":  (500,  4500),
    "Cardiology":   (800,  5000),
    "Orthopedics":  (600,  4800),
    "General":      (50,   1500),
    "Pediatrics":   (100,  2000),
}

APPOINTMENT_NOTES = [
    "Patient reported mild discomfort",
    "Follow-up required in 2 weeks",
    "Lab results pending",
    "Patient responded well to treatment",
    "Referred to specialist",
    "Prescription updated",
    "Advised lifestyle changes",
    "No significant findings",
    "Routine checkup completed",
    "Patient stable, continue medication",
]


# ── Helpers ──────────────────────────────────────────────────────────────────
def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def rand_datetime(start: date, end: date) -> str:
    d = rand_date(start, end)
    h = random.choice([9, 10, 11, 12, 14, 15, 16, 17])
    m = random.choice([0, 15, 30, 45])
    return datetime(d.year, d.month, d.day, h, m).strftime("%Y-%m-%d %H:%M:%S")


def maybe_null(value, prob_null: float = 0.15):
    """Return None with given probability to simulate missing data."""
    return None if random.random() < prob_null else value


def rand_phone() -> str:
    return f"+91-{random.randint(70000,99999)}{random.randint(10000,99999)}"


def rand_email(first: str, last: str) -> str:
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "rediffmail.com"]
    tag = random.randint(1, 999)
    return f"{first.lower()}.{last.lower()}{tag}@{random.choice(domains)}"


# ── Schema ───────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name        TEXT    NOT NULL,
    last_name         TEXT    NOT NULL,
    email             TEXT,
    phone             TEXT,
    date_of_birth     DATE,
    gender            TEXT,
    city              TEXT,
    registered_date   DATE
);

CREATE TABLE IF NOT EXISTS doctors (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    specialization   TEXT,
    department       TEXT,
    phone            TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER REFERENCES patients(id),
    doctor_id        INTEGER REFERENCES doctors(id),
    appointment_date DATETIME,
    status           TEXT,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS treatments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id    INTEGER REFERENCES appointments(id),
    treatment_name    TEXT,
    cost              REAL,
    duration_minutes  INTEGER
);

CREATE TABLE IF NOT EXISTS invoices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    INTEGER REFERENCES patients(id),
    invoice_date  DATE,
    total_amount  REAL,
    paid_amount   REAL,
    status        TEXT
);
"""


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    today      = date.today()
    year_ago   = today - timedelta(days=365)

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # ── Create schema ────────────────────────────────────────────────────────
    cur.executescript(SCHEMA)
    conn.commit()

    # ── 1. Doctors (15, 3 per specialization) ────────────────────────────────
    doctor_rows = []
    specs_cycle = [s for s in SPECIALIZATIONS for _ in range(3)]  # 15 slots
    for i, (first, last) in enumerate(DOCTOR_NAMES):
        spec  = specs_cycle[i]
        dept  = DEPARTMENTS[spec]
        phone = maybe_null(rand_phone(), 0.05)
        doctor_rows.append((f"{first} {last}", spec, dept, phone))

    cur.executemany(
        "INSERT INTO doctors (name, specialization, department, phone) VALUES (?,?,?,?)",
        doctor_rows,
    )
    conn.commit()

    cur.execute("SELECT id, specialization FROM doctors")
    doctors = cur.fetchall()                         # [(id, spec), ...]
    doctor_ids = [d[0] for d in doctors]
    doc_spec   = {d[0]: d[1] for d in doctors}       # id → specialization

    # ── 2. Patients (200) ────────────────────────────────────────────────────
    patient_rows = []
    used_names   = set()
    attempts     = 0
    while len(patient_rows) < 200 and attempts < 5000:
        attempts += 1
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        if (fn, ln) in used_names:
            continue
        used_names.add((fn, ln))

        gender  = random.choice(["M", "F"])
        dob     = rand_date(date(1950, 1, 1), date(2015, 12, 31))
        reg     = rand_date(year_ago, today)
        city    = random.choice(CITIES)
        email   = maybe_null(rand_email(fn, ln), 0.10)
        phone   = maybe_null(rand_phone(),        0.12)

        patient_rows.append((fn, ln, email, phone,
                             dob.isoformat(), gender, city, reg.isoformat()))

    cur.executemany(
        """INSERT INTO patients
           (first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
           VALUES (?,?,?,?,?,?,?,?)""",
        patient_rows,
    )
    conn.commit()

    cur.execute("SELECT id FROM patients")
    patient_ids = [r[0] for r in cur.fetchall()]

    # ── Skewed distributions ─────────────────────────────────────────────────
    # Some patients visit many times, some once
    patient_weights = []
    for pid in patient_ids:
        roll = random.random()
        if roll < 0.10:        # 10 % are frequent visitors
            patient_weights.append(12)
        elif roll < 0.30:      # 20 % are moderate visitors
            patient_weights.append(4)
        else:                  # 70 % visit rarely
            patient_weights.append(1)

    # Some doctors are busier
    doctor_weights = []
    for did in doctor_ids:
        roll = random.random()
        if roll < 0.20:
            doctor_weights.append(5)
        elif roll < 0.50:
            doctor_weights.append(2)
        else:
            doctor_weights.append(1)

    # ── 3. Appointments (500) ────────────────────────────────────────────────
    appt_statuses = ["Scheduled", "Completed", "Cancelled", "No-Show"]
    appt_status_weights = [0.15, 0.55, 0.18, 0.12]

    appointment_rows = []
    for _ in range(500):
        pid    = random.choices(patient_ids, weights=patient_weights)[0]
        did    = random.choices(doctor_ids,  weights=doctor_weights)[0]
        dt     = rand_datetime(year_ago, today)
        status = random.choices(appt_statuses, weights=appt_status_weights)[0]
        notes  = maybe_null(random.choice(APPOINTMENT_NOTES), 0.30)
        appointment_rows.append((pid, did, dt, status, notes))

    cur.executemany(
        """INSERT INTO appointments
           (patient_id, doctor_id, appointment_date, status, notes)
           VALUES (?,?,?,?,?)""",
        appointment_rows,
    )
    conn.commit()

    # Fetch completed appointments for treatments
    cur.execute(
        "SELECT id, doctor_id FROM appointments WHERE status = 'Completed'"
    )
    completed_appts = cur.fetchall()    # [(appt_id, doc_id), ...]

    # ── 4. Treatments (350, linked to completed appointments) ────────────────
    # Sample 350 from completed (or all if fewer than 350)
    sample_pool = completed_appts[:]
    random.shuffle(sample_pool)
    treatment_appts = sample_pool[:min(350, len(sample_pool))]

    treatment_rows = []
    for appt_id, doc_id in treatment_appts:
        spec     = doc_spec.get(doc_id, "General")
        tnames   = TREATMENT_NAMES.get(spec, TREATMENT_NAMES["General"])
        tname    = random.choice(tnames)
        lo, hi   = COST_RANGES.get(spec, (50, 2000))
        cost     = round(random.uniform(lo, hi), 2)
        duration = random.choice([15, 20, 30, 45, 60, 90])
        treatment_rows.append((appt_id, tname, cost, duration))

    cur.executemany(
        """INSERT INTO treatments
           (appointment_id, treatment_name, cost, duration_minutes)
           VALUES (?,?,?,?)""",
        treatment_rows,
    )
    conn.commit()

    # ── 5. Invoices (300) ────────────────────────────────────────────────────
    inv_statuses      = ["Paid", "Pending", "Overdue"]
    inv_status_weights = [0.55, 0.25, 0.20]

    # Pick 300 patients (allow repeats for patients with multiple visits)
    invoice_patient_ids = random.choices(patient_ids, weights=patient_weights, k=300)

    invoice_rows = []
    for pid in invoice_patient_ids:
        inv_date     = rand_date(year_ago, today)
        total        = round(random.uniform(50, 5000), 2)
        inv_status   = random.choices(inv_statuses, weights=inv_status_weights)[0]

        if inv_status == "Paid":
            paid = total
        elif inv_status == "Pending":
            paid = round(random.uniform(0, total * 0.5), 2)
        else:  # Overdue
            paid = round(random.uniform(0, total * 0.3), 2)

        invoice_rows.append((pid, inv_date.isoformat(), total, paid, inv_status))

    cur.executemany(
        """INSERT INTO invoices
           (patient_id, invoice_date, total_amount, paid_amount, status)
           VALUES (?,?,?,?,?)""",
        invoice_rows,
    )
    conn.commit()
    conn.close()

    # ── Summary ──────────────────────────────────────────────────────────────
    conn2 = sqlite3.connect(DB_PATH)
    c2    = conn2.cursor()

    counts = {}
    for tbl in ("patients", "doctors", "appointments", "treatments", "invoices"):
        c2.execute(f"SELECT COUNT(*) FROM {tbl}")
        counts[tbl] = c2.fetchone()[0]

    c2.execute("SELECT status, COUNT(*) FROM appointments GROUP BY status")
    appt_breakdown = dict(c2.fetchall())

    c2.execute("SELECT status, COUNT(*) FROM invoices GROUP BY status")
    inv_breakdown = dict(c2.fetchall())

    c2.execute("SELECT specialization, COUNT(*) FROM doctors GROUP BY specialization")
    doc_breakdown = dict(c2.fetchall())

    conn2.close()

    print("=" * 60)
    print("  Clinic Management DB — Setup Complete")
    print("=" * 60)
    print(f"  Database : {DB_PATH}")
    print(f"  Created  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    print(f"  Patients     : {counts['patients']:>4}")
    print(f"  Doctors      : {counts['doctors']:>4}  ", end="")
    print("  |  ".join(f"{s}: {n}" for s, n in sorted(doc_breakdown.items())))
    print(f"  Appointments : {counts['appointments']:>4}  ", end="")
    print("  |  ".join(f"{s}: {n}" for s, n in sorted(appt_breakdown.items())))
    print(f"  Treatments   : {counts['treatments']:>4}")
    print(f"  Invoices     : {counts['invoices']:>4}  ", end="")
    print("  |  ".join(f"{s}: {n}" for s, n in sorted(inv_breakdown.items())))
    print("=" * 60)
    print(f"  Created {counts['patients']} patients, {counts['doctors']} doctors,")
    print(f"  {counts['appointments']} appointments, {counts['treatments']} treatments,")
    print(f"  {counts['invoices']} invoices.")
    print("=" * 60)


if __name__ == "__main__":
    main()
