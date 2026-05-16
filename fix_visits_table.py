import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

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

conn.commit()
conn.close()

print("Visits table created successfully")