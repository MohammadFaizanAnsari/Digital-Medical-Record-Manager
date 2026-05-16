import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# ------------------ DOCTORS TABLE ------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    clinic_name TEXT,
    clinic_address TEXT
)
""")
print("Doctors table created successfully!")

# ------------------ PATIENTS TABLE ------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER,
    name TEXT,
    age INTEGER,
    gender TEXT,
    phone TEXT,
    email TEXT,
    disease TEXT,
    blood_group TEXT,
    address TEXT,
    report TEXT
)
""")

# ------------------ APPOINTMENTS TABLE ------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER,
    doctor_id INTEGER,
    patient_name TEXT,
    requested_date TEXT,
    status TEXT DEFAULT 'pending',
    message TEXT,
    FOREIGN KEY(patient_id) REFERENCES patients(id),
    FOREIGN KEY(doctor_id) REFERENCES doctors(id)
)
""")
print("Appointments table created successfully!")

# ------------------ MEDICINES TABLE ------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER,
    medicine_name TEXT,
    dosage TEXT,
    times_per_day INTEGER,
    total_days INTEGER,
    quantity INTEGER,
    start_date TEXT,
    reminder_sent INTEGER DEFAULT 0
)
""")

# ------------------ VISITS TABLE ------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER,
    visit_date TEXT,
    diagnosis TEXT,
    prescription TEXT,
    FOREIGN KEY(patient_id) REFERENCES patients(id)
)
""")
print("Visits table created successfully!")

# ------------------ CREATE DEFAULT DOCTOR ------------------
cur.execute("""
INSERT INTO doctors (name, email, password, clinic_name, clinic_address)
VALUES (?, ?, ?, ?, ?)
""", (
    "Admin Doctor",
    "doctor@gmail.com",
    "1234",
    "City Clinic",
    "Main Road"
))

print("Default doctor created!")

conn.commit()
conn.close()

print("✅ Database setup completed successfully!")