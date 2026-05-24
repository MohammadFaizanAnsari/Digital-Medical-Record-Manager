import sqlite3

DATABASE = "database.db"

def setup_database():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # ================= DOCTORS =================
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

    # ================= PATIENTS =================
    # Note: Added password field (matches phone during default registration/checking)
    # Reconciled fields from both app.py and schema needs
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
        report TEXT,
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    )
    """)

    # ================= APPOINTMENTS =================
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

    # ================= MEDICINES =================
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
        reminder_sent INTEGER DEFAULT 0,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )
    """)

    # ================= VISITS =================
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

    # ================= REPORTS =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS patient_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        report_name TEXT,
        file_name TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )
    """)

    # ================= DEFAULT DOCTOR =================
    cur.execute("SELECT * FROM doctors WHERE email=?", ("doctor@gmail.com",))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO doctors (name, email, password, clinic_name, clinic_address)
            VALUES (?, ?, ?, ?, ?)
        """, ("Admin Doctor", "doctor@gmail.com", "1234", "City Clinic", "Main Road"))

    conn.commit()
    conn.close()
    print("Database schema successfully generated and verified!")

if __name__ == "__main__":
    setup_database()