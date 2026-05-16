import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# Add columns for medicine and refill date
cur.execute("ALTER TABLE patients ADD COLUMN medicine TEXT")
cur.execute("ALTER TABLE patients ADD COLUMN refill_date TEXT")

conn.commit()
conn.close()

print("Columns added successfully!")