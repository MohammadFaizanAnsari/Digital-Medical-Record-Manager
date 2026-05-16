import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# Add patient_name column if it doesn't exist
try:
    cur.execute("ALTER TABLE appointments ADD COLUMN patient_name TEXT")
    print("Column 'patient_name' added successfully!")
except sqlite3.OperationalError:
    print("Column 'patient_name' already exists.")

conn.commit()
conn.close()