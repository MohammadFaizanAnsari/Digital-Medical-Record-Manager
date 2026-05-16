import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from datetime import datetime, timedelta
from twilio.rest import Client
import schedule
import time
import threading

import smtplib
from email.mime.text import MIMEText

EMAIL_ADDRESS = "fa735594@gmail.com"
EMAIL_PASSWORD = "krfm bkgo ihnc ptyn"

def send_email(to_email, subject, message):

    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DATABASE = "database.db"

# ---------------- LOGIN CHECK ----------------
def is_logged_in():
    return session.get("logged_in")

# ---------------- DATABASE INIT ----------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Patients Table
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
        medicine TEXT,
        refill_date TEXT
    )
""")

    # Visits Table
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

    # Appointments Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            requested_date TEXT,
            status TEXT DEFAULT 'pending',
            patient_name TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id)
        )
    """)

    # Medicines Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            medicine_name TEXT,
            dosage TEXT,
            times_per_day INTEGER,
            total_days INTEGER,
            quantity INTEGER,
            start_date TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- SERVE UPLOADED FILES ----------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/login")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # ---------------- DOCTOR LOGIN ----------------
        if role == "admin":

            cur.execute(
                "SELECT * FROM doctors WHERE email=? AND password=?",
                (username, password)
            )

            doctor = cur.fetchone()

            if doctor:
                session["logged_in"] = True
                session["role"] = "admin"
                session["doctor_id"] = doctor["id"]

                conn.close()
                return redirect("/dashboard")

            else:
                conn.close()
                flash("Invalid Email or Password")
                return redirect("/login")

        # ---------------- PATIENT LOGIN ----------------
        elif role == "patient":

            cur.execute(
                "SELECT * FROM patients WHERE email=? AND phone=?",
                (username, password)
            )

            patient = cur.fetchone()

            if patient:
                session["logged_in"] = True
                session["role"] = "patient"
                session["patient_id"] = patient["id"]

                conn.close()
                return redirect("/patient_dashboard")

            else:
                conn.close()
                flash("Invalid Email or Phone Number")
                return redirect("/login")

    return render_template("login.html")


# ---------------- DOCTOR REGISTRATION ----------------
@app.route("/register_doctor", methods=["GET", "POST"])
def register_doctor():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        clinic = request.form["clinic"]
        address = request.form["address"]

        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # -------- CHECK IF EMAIL ALREADY EXISTS --------
        cur.execute("SELECT * FROM doctors WHERE email=?", (email,))
        existing_doctor = cur.fetchone()

        if existing_doctor:
            conn.close()
            flash("This email already exists. Please use another email.")
            return redirect("/register_doctor")

        # -------- INSERT NEW DOCTOR --------
        cur.execute("""
            INSERT INTO doctors (name, email, password, clinic_name, clinic_address)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, password, clinic, address))

        conn.commit()
        conn.close()

        flash("Doctor account created successfully! Please login.")
        return redirect("/login")

    return render_template("doctor_register.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    if not is_logged_in():
        return redirect("/login")

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row   # IMPORTANT for using column names in HTML
    cur = conn.cursor()

    doctor_id = session.get("doctor_id")

    # Doctor info
    cur.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,))
    doctor = cur.fetchone()

    # Total patients
    cur.execute("SELECT COUNT(*) FROM patients WHERE doctor_id=?", (doctor_id,))
    total_patients = cur.fetchone()[0]

    # Total visits
    cur.execute("SELECT COUNT(*) FROM visits")
    total_visits = cur.fetchone()[0]

    # Pending appointments count
    cur.execute("SELECT COUNT(*) FROM appointments WHERE status='pending'")
    pending_appointments = cur.fetchone()[0]

    # Recent patients
    cur.execute("""
        SELECT name, age, phone
        FROM patients
        WHERE doctor_id=?
        ORDER BY id DESC
        LIMIT 5
    """, (doctor_id,))
    
    recent_patients = cur.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        doctor=doctor,
        total_patients=total_patients,
        total_visits=total_visits,
        recent_patients=recent_patients,
        pending_appointments=pending_appointments
    )
    
# ---------------- ADD PATIENT ----------------
@app.route("/add_patient", methods=["GET", "POST"])
def add_patient():

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    if request.method == "POST":

        name = request.form["name"]
        age = request.form["age"]
        gender = request.form["gender"]
        phone = request.form["phone"]
        email = request.form["email"]
        disease = request.form["disease"]
        blood = request.form["blood_group"]
        address = request.form["address"]

        # 👇 get logged-in doctor id
        doctor_id = session["doctor_id"]

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO patients
        (doctor_id, name, age, gender, phone, email, disease, blood_group, address)
        VALUES (?,?,?,?,?,?,?,?,?)
        """, (doctor_id, name, age, gender, phone, email, disease, blood, address))

        conn.commit()
        conn.close()

        flash("Patient added successfully")
        return redirect("/patients")

    return render_template("add_patient.html")

# ---------------- VIEW PATIENTS ----------------
@app.route("/patients")
def view_patients():

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    search = request.args.get("search")

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # get logged in doctor id
    doctor_id = session["doctor_id"]

    if search:
        cur.execute(
            """
            SELECT * FROM patients 
            WHERE doctor_id=? AND (name LIKE ? OR phone LIKE ?)
            """,
            (doctor_id, '%' + search + '%', '%' + search + '%')
        )
    else:
        cur.execute(
            "SELECT * FROM patients WHERE doctor_id=?",
            (doctor_id,)
        )

    patients = cur.fetchall()
    conn.close()

    return render_template("patient_list.html", patients=patients)

# ---------------- EDIT PATIENT ----------------
@app.route("/edit_patient/<int:patient_id>", methods=["GET","POST"])
def edit_patient(patient_id):

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔥 FETCH PATIENT FIRST (IMPORTANT)
    cur.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
    patient = cur.fetchone()

    if request.method == "POST":

        name = request.form["name"]
        age = request.form["age"]
        gender = request.form["gender"]
        phone = request.form["phone"]
        email = request.form["email"]
        disease = request.form["disease"]
        blood_group = request.form["blood_group"]
        address = request.form["address"]

        file = request.files.get("report_file")

        # ✅ keep old report if no new file
        report_filename = patient["report"]

        # ✅ upload new file
        if file and file.filename != "":
            filename = file.filename
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            report_filename = filename

        # ✅ UPDATE DB
        cur.execute("""
            UPDATE patients
            SET name=?, age=?, gender=?, phone=?, email=?, disease=?, blood_group=?, address=?, report=?
            WHERE id=?
        """, (name, age, gender, phone, email, disease, blood_group, address, report_filename, patient_id))

        conn.commit()
        conn.close()

        flash("Patient updated successfully")
        return redirect("/patients")

    conn.close()

    return render_template("edit_patient.html", patient=patient)

# ---------------- DELETE PATIENT ----------------
@app.route("/delete_patient/<int:patient_id>", methods=["POST"])
def delete_patient(patient_id):

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    cur.execute("DELETE FROM patients WHERE id=?", (patient_id,))

    conn.commit()
    conn.close()

    flash("Patient deleted successfully!")
    return redirect("/patients")

# ---------------- PATIENT PROFILE ----------------
@app.route("/patient/<int:id>")
def patient_profile(id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # patient info
    cur.execute("SELECT * FROM patients WHERE id=?", (id,))
    patient = cur.fetchone()

    # medicines
    cur.execute("SELECT * FROM medicines WHERE patient_id=?", (id,))
    medicines = cur.fetchall()

    # visits
    cur.execute("SELECT * FROM visits WHERE patient_id=?", (id,))
    visits = cur.fetchall()

    updated_medicines = []
    for med in medicines:
        start_date = med["start_date"]
        duration = med["total_days"]
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = start + timedelta(days=int(duration))
        today = datetime.now()

        if today > end:
            status = "Finished ❌"
        else:
            days_left = (end - today).days
            if days_left == 0:
                status = "Finishing Today ⚠️"
            elif days_left == 1:
                status = "Finishing Tomorrow ⚠️"
            else:
                status = f"{days_left} days left"

        updated_medicines.append({
            "medicine_name": med["medicine_name"],
            "dosage": med["dosage"],
            "start_date": start_date,
            "duration": duration,
            "status": status
        })

    conn.close()
    return render_template(
        "patient_profile.html",
        patient=patient,
        medicines=updated_medicines,
        visits=visits
    )

# ---------------- PATIENT DASHBOARD ----------------
@app.route("/patient_dashboard")
def patient_dashboard():
    if not is_logged_in() or session.get("role") != "patient":
        return redirect("/login")

    patient_id = session.get("patient_id")
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    cur.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
    patient = cur.fetchone()

    cur.execute("SELECT * FROM visits WHERE patient_id=?", (patient_id,))
    visits = cur.fetchall()

    cur.execute("SELECT * FROM medicines WHERE patient_id=?", (patient_id,))
    meds = cur.fetchall()

    medicine_alerts = []
    today = datetime.today()
    for med in meds:
        start = datetime.strptime(med[7], "%Y-%m-%d")
        refill = start + timedelta(days=med[5])
        days_left = (refill - today).days

        if days_left < 0:
            msg = f"{med[2]} ran out {abs(days_left)} days ago"
        elif days_left == 0:
            msg = f"{med[2]} will run out today"
        elif days_left == 1:
            msg = f"{med[2]} will run out tomorrow"
        elif days_left <= 3:
            msg = f"{med[2]} will run out in {days_left} days"
        else:
            msg = f"{med[2]} refill on {refill.strftime('%Y-%m-%d')}"

        medicine_alerts.append(msg)

    cur.execute("SELECT * FROM appointments WHERE patient_id=? ORDER BY id DESC", (patient_id,))
    appointments = cur.fetchall()
    conn.close()

    return render_template(
        "patient_dashboard.html",
        patient=patient,
        visits=visits,
        medicine_alerts=medicine_alerts,
        appointments=appointments
    )

# ---------------- REQUEST APPOINTMENT ----------------
@app.route("/request_appointment", methods=["GET", "POST"])
def request_appointment():

    if not is_logged_in() or session.get("role") != "patient":
        return redirect("/login")

    patient_id = session.get("patient_id")

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get patient details
    cur.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
    patient = cur.fetchone()

    if request.method == "POST":

        requested_date = request.form.get("requested_date")

        # Get assigned doctor id from patient table
        doctor_id = patient["doctor_id"]

        # Insert appointment with doctor_id
        cur.execute("""
            INSERT INTO appointments
            (patient_id, doctor_id, requested_date, patient_name)
            VALUES (?, ?, ?, ?)
        """, (
            patient_id,
            doctor_id,
            requested_date,
            patient["name"]
        ))

        conn.commit()

        # -------- SEND EMAIL --------
        patient_email = patient["email"]
        patient_name = patient["name"]

        subject = "Appointment Request Received"

        message = f"""
Hello {patient_name},

Your appointment request for {requested_date} has been received successfully.

The doctor will review it soon.

You can check your appointment status here:
http://127.0.0.1:5000/patient_auto_login/{patient_id}

Thank you,
Digital Medical Record System
"""

        # Send email only if valid
        if patient_email and "@" in patient_email:
            send_email(patient_email, subject, message)

        flash("Appointment requested successfully!")

        conn.close()
        return redirect("/patient_dashboard")

    conn.close()

    return render_template(
        "request_appointment.html",
        patient=patient
    )


# ---------------- VIEW APPOINTMENTS ----------------
@app.route("/appointments")
def view_appointments():

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    doctor_id = session.get("doctor_id")

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ONLY THIS DOCTOR'S APPOINTMENTS
    cur.execute("""
        SELECT *
        FROM appointments
        WHERE doctor_id=?
        ORDER BY id DESC
    """, (doctor_id,))

    appointments = cur.fetchall()

    conn.close()

    return render_template(
        "appointments.html",
        appointments=appointments
    )


# ---------------- APPROVE APPOINTMENT ----------------
@app.route("/appointments/<int:id>/approve", methods=["POST"])
def approve_appointment(id):

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    doctor_id = session.get("doctor_id")

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check appointment belongs to logged-in doctor
    cur.execute("""
        SELECT *
        FROM appointments
        WHERE id=? AND doctor_id=?
    """, (id, doctor_id))

    appointment = cur.fetchone()

    if not appointment:
        conn.close()
        flash("Unauthorized access!")
        return redirect("/appointments")

    # Update status
    cur.execute("""
        UPDATE appointments
        SET status='approved'
        WHERE id=?
    """, (id,))

    # Get patient info
    patient_id = appointment["patient_id"]

    cur.execute("""
        SELECT name, email
        FROM patients
        WHERE id=?
    """, (patient_id,))

    patient = cur.fetchone()

    conn.commit()
    conn.close()

    patient_name = patient["name"]
    patient_email = patient["email"]

    subject = "Appointment Approved"

    message = f"""
Hello {patient_name},

Good news! 🎉

Your appointment has been APPROVED by the doctor.

Click below to view your dashboard:
http://127.0.0.1:5000/patient_auto_login/{patient_id}

Thank you,
Digital Medical Record System
"""

    if patient_email and "@" in patient_email:
        send_email(patient_email, subject, message)

    flash("Appointment approved and patient notified!")

    return redirect("/appointments")


# ---------------- REJECT APPOINTMENT ----------------
@app.route("/appointments/<int:id>/reject", methods=["POST"])
def reject_appointment(id):

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    doctor_id = session.get("doctor_id")

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check appointment belongs to logged-in doctor
    cur.execute("""
        SELECT *
        FROM appointments
        WHERE id=? AND doctor_id=?
    """, (id, doctor_id))

    appointment = cur.fetchone()

    if not appointment:
        conn.close()
        flash("Unauthorized access!")
        return redirect("/appointments")

    # Update status
    cur.execute("""
        UPDATE appointments
        SET status='rejected'
        WHERE id=?
    """, (id,))

    # Get patient info
    patient_id = appointment["patient_id"]

    cur.execute("""
        SELECT name, email
        FROM patients
        WHERE id=?
    """, (patient_id,))

    patient = cur.fetchone()

    conn.commit()
    conn.close()

    patient_name = patient["name"]
    patient_email = patient["email"]

    subject = "Appointment Rejected"

    message = f"""
Hello {patient_name},

Unfortunately your appointment request has been rejected.

Please select another date for your visit.

You can request a new appointment here:
http://127.0.0.1:5000/patient_auto_login/{patient_id}

Thank you,
Digital Medical Record System
"""

    if patient_email and "@" in patient_email:
        send_email(patient_email, subject, message)

    flash("Appointment rejected and patient notified!")

    return redirect("/appointments")

# ---------------- APPOINTMENT CALENDAR PAGE ----------------
@app.route("/appointment_calendar")
def appointment_calendar():

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    return render_template("appointment_calendar.html")

# ---------------- CALENDAR DATA ----------------
@app.route("/appointment_calendar_data")
def appointment_calendar_data():

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    doctor_id = session.get("doctor_id")

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # ONLY THIS DOCTOR'S APPOINTMENTS
    cur.execute("""
        SELECT requested_date, COUNT(*)
        FROM appointments
        WHERE status != 'rejected'
        AND doctor_id=?
        GROUP BY requested_date
    """, (doctor_id,))

    data = cur.fetchall()

    conn.close()

    events = []

    for row in data:

        date = row[0]
        count = row[1]

        if count <= 2:
            color = "green"
        elif count <= 5:
            color = "orange"
        else:
            color = "red"

        events.append({
            "title": f"{count} appointments",
            "start": date,
            "color": color
        })

    from flask import jsonify
    return jsonify(events)

# ---------------- APPOINTMENTS BY DATE ----------------
@app.route("/appointments_by_date")
def appointments_by_date():

    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    date = request.args.get("date")

    doctor_id = session.get("doctor_id")

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ONLY THIS DOCTOR'S APPOINTMENTS
    cur.execute("""
        SELECT p.name, p.phone, a.status
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        WHERE a.requested_date = ?
        AND a.status != 'rejected'
        AND a.doctor_id = ?
    """, (date, doctor_id))

    rows = cur.fetchall()

    conn.close()

    appointments = []

    for r in rows:
        appointments.append({
            "name": r["name"],
            "phone": r["phone"],
            "status": r["status"]
        })

    return {"appointments": appointments}

# ---------------- ADD MEDICINE ----------------
@app.route("/add_medicine/<int:patient_id>", methods=["POST"])
def add_medicine(patient_id):
    medicine_name = request.form["medicine_name"]
    dosage = request.form["dosage"]
    times_per_day = request.form["times_per_day"]
    total_days = request.form["total_days"]
    quantity = request.form["quantity"]
    start_date = request.form["start_date"]

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO medicines (patient_id, medicine_name, dosage, times_per_day, total_days, quantity, start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (patient_id, medicine_name, dosage, times_per_day, total_days, quantity, start_date))
    conn.commit()
    conn.close()
    flash("Medicine added successfully!")
    return redirect(url_for("patient_profile", id=patient_id))

# ---------------- ADD VISIT ----------------
@app.route("/add_visit/<int:patient_id>", methods=["POST"])
def add_visit(patient_id):
    visit_date = request.form["visit_date"]
    diagnosis = request.form["diagnosis"]
    prescription = request.form["prescription"]

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO visits (patient_id, visit_date, diagnosis, prescription)
        VALUES (?, ?, ?, ?)
    """, (patient_id, visit_date, diagnosis, prescription))
    conn.commit()
    conn.close()
    flash("Visit record saved successfully!")
    return redirect(url_for("patient_profile", id=patient_id))

# ---------------- Medicine Refill Reminder EMAIL -------------------
def check_medicine_refills():

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    today = datetime.now().date()

    cur.execute("""
        SELECT m.*, p.name as patient_name, p.email
        FROM medicines m
        JOIN patients p ON m.patient_id = p.id
    """)

    medicines = cur.fetchall()

    for med in medicines:

        start_date = datetime.strptime(med["start_date"], "%Y-%m-%d").date()
        end_date = start_date + timedelta(days=med["total_days"])
        days_left = (end_date - today).days

        print("Checking:", med["medicine_name"], "Days left:", days_left)

        # -------- MEDICINE ABOUT TO FINISH --------
        if 0 <= days_left <= 3 and med["reminder_sent"] == 0:

            subject = "Medicine Refill Reminder"

            message = f"""
Hello {med['patient_name']},

Your medicine "{med['medicine_name']}" will run out in {days_left} day(s).

Please plan a refill to continue your treatment.

View your dashboard here:
http://127.0.0.1:5000/patient_auto_login/{med['patient_id']}

Thank you,
Digital Medical Record System
"""

            send_email(med["email"], subject, message)

            # Mark reminder as sent
            cur.execute(
                "UPDATE medicines SET reminder_sent = 1 WHERE id = ?",
                (med["id"],)
            )
            conn.commit()

        # -------- MEDICINE FINISHED --------
        elif days_left < 0:

            subject = "Medicine Course Finished"

            message = f"""
Hello {med['patient_name']},

Your medicine "{med['medicine_name']}" course has finished.

If required, please consult your doctor for a refill.

View your dashboard here:
http://127.0.0.1:5000/patient_auto_login/{med['patient_id']}

Thank you,
Digital Medical Record System
"""

            send_email(med["email"], subject, message)

    conn.close()


# ------------------ Auto Login via Email ------------------
@app.route("/patient_auto_login/<int:patient_id>")
def patient_auto_login(patient_id):

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    cur.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
    patient = cur.fetchone()
    conn.close()

    if patient:
        session["logged_in"] = True
        session["role"] = "patient"
        session["patient_id"] = patient_id

        return redirect("/patient_dashboard")

    return "Invalid link"


# ---------------- Scheduler ----------------
def run_scheduler():

    # schedule.every().day.at("08:00").do(check_medicine_refills)
    schedule.every(1).minutes.do(check_medicine_refills)

    while True:
        schedule.run_pending()
        time.sleep(60)


threading.Thread(target=run_scheduler, daemon=True).start()


# # ---------------- TEST MEDICINE REFILL ----------------
# @app.route("/test_refill")
# def test_refill():
#     check_medicine_refills()
#     return "Medicine refill check executed!"

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)