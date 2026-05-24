import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
from datetime import datetime, timedelta
import schedule
import time
import threading

import smtplib
from email.mime.text import MIMEText

EMAIL_ADDRESS = "fa735594@gmail.com"
EMAIL_PASSWORD = "krfm bkgo ihnc ptyn"

def send_email(to_email, subject, message):
    try:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email.strip()

        print(f"📡 [SMTP CONNECT] Connecting to Gmail for: {to_email.strip()}...")
        # Using port 587 with starttls ensures cloud provider firewalls don't silently block the connection
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ [SMTP SUCCESS] Message delivered successfully to {to_email.strip()}")
    except Exception as e:
        print(f"❌ [SMTP ERROR] Failed to send email to {to_email.strip()}: {e}")

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
    from create_db import setup_database
    setup_database()

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

        conn = sqlite3.connect(DATABASE, timeout=20)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if role == "admin":
            cur.execute("SELECT * FROM doctors WHERE email=? AND password=?", (username, password))
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

        elif role == "patient":
            cur.execute("SELECT * FROM patients WHERE email=? AND phone=?", (username, password))
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

        conn = sqlite3.connect(DATABASE, timeout=20)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM doctors WHERE email=?", (email,))
        existing_doctor = cur.fetchone()

        if existing_doctor:
            conn.close()
            flash("This email already exists. Please use another email.")
            return redirect("/register_doctor")

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
    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row   
    cur = conn.cursor()

    doctor_id = session.get("doctor_id")

    cur.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,))
    doctor = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM patients WHERE doctor_id=?", (doctor_id,))
    total_patients = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM visits WHERE patient_id IN (SELECT id FROM patients WHERE doctor_id=?)", (doctor_id,))
    total_visits = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM appointments WHERE status='pending' AND doctor_id=?", (doctor_id,))
    pending_appointments = cur.fetchone()[0]

    cur.execute("""
        SELECT id, name, age, phone
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
        doctor_id = session["doctor_id"]

        conn = sqlite3.connect(DATABASE, timeout=20)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO patients (doctor_id, name, age, gender, phone, email, disease, blood_group, address, report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (doctor_id, name, age, gender, phone, email, disease, blood, address, ""))
        
        patient_id = cur.lastrowid

        files = request.files.getlist("reports[]")
        names = request.form.getlist("report_names[]")

        for i, file in enumerate(files):
            if file and file.filename != "":
                filename = file.filename
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                report_name = names[i] if (i < len(names) and names[i]) else filename
                cur.execute("""
                    INSERT INTO patient_reports (patient_id, report_name, file_name)
                    VALUES (?, ?, ?)
                """, (patient_id, report_name, filename))

        conn.commit()
        conn.close()

        flash("Patient added successfully along with reports!")
        return redirect("/patients")

    return render_template("add_patient.html")

# ---------------- VIEW PATIENTS ----------------
@app.route("/patients")
def view_patients():
    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    search = request.args.get("search")

    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    doctor_id = session["doctor_id"]

    if search:
        cur.execute("""
            SELECT * FROM patients 
            WHERE doctor_id=? AND (name LIKE ? OR phone LIKE ?)
        """, (doctor_id, '%' + search + '%', '%' + search + '%'))
    else:
        cur.execute("SELECT * FROM patients WHERE doctor_id=?", (doctor_id,))

    patients = cur.fetchall()
    conn.close()
    return render_template("patient_list.html", patients=patients)

# ---------------- EDIT PATIENT ----------------
@app.route("/edit_patient/<int:patient_id>", methods=["GET","POST"])
def edit_patient(patient_id):
    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

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

        cur.execute("""
            UPDATE patients
            SET name=?, age=?, gender=?, phone=?, email=?, disease=?, blood_group=?, address=?
            WHERE id=?
        """, (name, age, gender, phone, email, disease, blood_group, address, patient_id))

        files = request.files.getlist("reports[]")
        names = request.form.getlist("report_names[]")

        for i, file in enumerate(files):
            if file and file.filename != "":
                filename = file.filename
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                report_name = names[i] if (i < len(names) and names[i]) else filename
                cur.execute("""
                    INSERT INTO patient_reports (patient_id, report_name, file_name)
                    VALUES (?, ?, ?)
                """, (patient_id, report_name, filename))

        conn.commit()
        conn.close()

        flash("Patient records and files updated successfully!")
        return redirect("/patients")

    conn.close()
    return render_template("edit_patient.html", patient=patient)

# ---------------- DELETE PATIENT ----------------
@app.route("/delete_patient/<int:patient_id>", methods=["POST"])
def delete_patient(patient_id):
    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect(DATABASE, timeout=20)
    cur = conn.cursor()
    cur.execute("DELETE FROM patients WHERE id=?", (patient_id,))
    conn.commit()
    conn.close()

    flash("Patient deleted successfully!")
    return redirect("/patients")

# ---------------- PATIENT PROFILE ----------------
@app.route("/patient/<int:id>")
def patient_profile(id):
    if not is_logged_in():
        return redirect("/login")

    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM patients WHERE id=?", (id,))
    patient = cur.fetchone()

    cur.execute("SELECT * FROM patient_reports WHERE patient_id=? ORDER BY uploaded_at DESC", (id,))
    reports = cur.fetchall()

    cur.execute("SELECT * FROM medicines WHERE patient_id=?", (id,))
    medicines = cur.fetchall()

    cur.execute("SELECT * FROM visits WHERE patient_id=? ORDER BY visit_date DESC", (id,))
    visits = cur.fetchall()

    updated_medicines = []
    for med in medicines:
        try:
            start_date = med["start_date"]
            duration = med["total_days"]
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = start + timedelta(days=int(duration))
            today = datetime.now()

            if today > end:
                status = "Finished ❌"
            else:
                days_left = (end - today).days
                if days_left <= 0:
                    status = "Finishing Today ⚠️"
                elif days_left == 1:
                    status = "Finishing Tomorrow ⚠️"
                else:
                    status = f"{days_left} days left"
        except Exception:
            status = "Unknown"
            start_date = med["start_date"]
            duration = med["total_days"]

        updated_medicines.append({
            "medicine_name": med["medicine_name"],
            "dosage": med["dosage"],
            "times_per_day": med["times_per_day"],
            "quantity": med["quantity"],
            "start_date": start_date,
            "duration": duration,
            "status": status
        })

    conn.close()
    return render_template(
        "patient_profile.html",
        patient=patient,
        reports=reports,
        medicines=updated_medicines,
        visits=visits
    )

# ---------------- PATIENT DASHBOARD ----------------
@app.route("/patient_dashboard")
def patient_dashboard():
    if not is_logged_in() or session.get("role") != "patient":
        return redirect("/login")

    patient_id = session.get("patient_id")
    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row  
    cur = conn.cursor()

    cur.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
    patient = cur.fetchone()

    cur.execute("SELECT * FROM visits WHERE patient_id=? ORDER BY visit_date DESC", (patient_id,))
    visits = cur.fetchall()

    cur.execute("SELECT * FROM medicines WHERE patient_id=?", (patient_id,))
    medicines = cur.fetchall()

    cur.execute("SELECT * FROM patient_reports WHERE patient_id=? ORDER BY uploaded_at DESC", (patient_id,))
    reports = cur.fetchall()

    medicine_alerts = []
    today = datetime.today()
    for med in medicines:
        try:
            start = datetime.strptime(med["start_date"], "%Y-%m-%d")
            refill = start + timedelta(days=int(med["total_days"]))
            days_left = (refill - today).days

            if days_left < 0:
                msg = f"{med['medicine_name']} ran out {abs(days_left)} days ago"
            elif days_left == 0:
                msg = f"{med['medicine_name']} will run out today"
            elif days_left == 1:
                msg = f"{med['medicine_name']} will run out tomorrow"
            elif days_left <= 3:
                msg = f"{med['medicine_name']} will run out in {days_left} days"
            else:
                msg = f"{med['medicine_name']} refill on {refill.strftime('%Y-%m-%d')}"
            
            medicine_alerts.append(msg)
        except Exception as e:
            print(f"Error calculating alerts for {med['medicine_name']}: {e}")

    # Fetches all submitted requests for display in the table
    cur.execute("SELECT * FROM appointments WHERE patient_id=? ORDER BY id DESC", (patient_id,))
    appointments = cur.fetchall()
    
    conn.close()

    return render_template(
        "patient_dashboard.html",
        patient=patient,
        visits=visits,
        medicines=medicines,       
        reports=reports,          
        medicine_alerts=medicine_alerts,
        appointments=appointments
    )

# ---------------- REQUEST APPOINTMENT ----------------
@app.route("/request_appointment", methods=["GET", "POST"])
def request_appointment():
    if not is_logged_in() or session.get("role") != "patient":
        return redirect("/login")

    patient_id = session.get("patient_id")
    
    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
    patient = cur.fetchone()

    if request.method == "POST":
        requested_date = request.form.get("requested_date")
        doctor_id = patient["doctor_id"]

        cur.execute("""
            INSERT INTO appointments (patient_id, doctor_id, requested_date, patient_name, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (patient_id, doctor_id, requested_date, patient["name"]))
        conn.commit()

        patient_email = patient["email"]
        patient_name = patient["name"]
        
        subject = "Appointment Request Received Successfully"
        message = f"Hello {patient_name},\n\nYour appointment request for {requested_date} has been received successfully.\n\nThank you!"

        if patient_email and "@" in str(patient_email):
            # Process directly in-line to bypass Render thread termination limits
            send_email(patient_email, subject, message)

        flash("Appointment requested successfully!")
        conn.close()
        return redirect("/patient_dashboard")

    conn.close()
    return render_template("request_appointment.html", patient=patient)


# ---------------- VIEW APPOINTMENTS ----------------
@app.route("/appointments")
def view_appointments():
    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    doctor_id = session.get("doctor_id")
    conn = sqlite3.connect(DATABASE, timeout=20)
    
    # CRITICAL: Do NOT use row_factory = sqlite3.Row if your template expects 
    # tuple indices like app[0], app[1], app[3], app[4], app[5]
    cur = conn.cursor()

    # Matches database index lookup mapping used in appointments.html template
    cur.execute("""
        SELECT id, patient_id, doctor_id, patient_name, requested_date, status 
        FROM appointments 
        WHERE doctor_id=? 
        ORDER BY id DESC
    """, (doctor_id,))
    appointments = cur.fetchall()
    conn.close()
    return render_template("appointments.html", appointments=appointments)

# ---------------- APPROVE APPOINTMENT ----------------
@app.route("/appointments/<int:id>/approve", methods=["POST"])
def approve_appointment(id):
    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT a.requested_date, p.name, p.email 
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.id 
        WHERE a.id = ?
    """, (id,))
    appointment_data = cur.fetchone()

    cur.execute("UPDATE appointments SET status='approved' WHERE id=?", (id,))
    conn.commit()

    if appointment_data:
        patient_email = appointment_data["email"]
        patient_name = appointment_data["name"]
        requested_date = appointment_data["requested_date"]

        subject = "Appointment Approved Successfully"
        message = f"Hello {patient_name},\n\nYour appointment request for {requested_date} has been approved successfully."

        if patient_email and "@" in str(patient_email):
            # Process directly in-line to prevent Render thread lifecycle cutoff
            send_email(patient_email, subject, message)

    flash("Appointment approved successfully!")
    conn.close()
    return redirect("/appointments")

# ---------------- REJECT APPOINTMENT ----------------
@app.route("/appointments/<int:id>/reject", methods=["POST"])
def reject_appointment(id):
    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT p.id as patient_db_id, p.name, p.email, a.requested_date
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.id 
        WHERE a.id = ?
    """, (id,))
    appointment_data = cur.fetchone()

    cur.execute("UPDATE appointments SET status='rejected' WHERE id=?", (id,))
    conn.commit()

    if appointment_data:
        patient_email = appointment_data["email"]
        patient_name = appointment_data["name"]
        patient_id = appointment_data["patient_db_id"]

        # Dynamically build the absolute auto-login return loop path 
        direct_link = f"{request.host_url.rstrip('/')}/patient_auto_login/{patient_id}"
        subject = "Appointment Request Update - Rejected"
        
        message = (
            f"Hello {patient_name},\n\n"
            f"Your selected date slot reached maximum appointments so your request is rejected.\n\n"
            f"Please Choose another date from link below:\n"
            f"{direct_link}\n\n"
            f"Thank you,\nClinical Administration"
        )

        if patient_email and "@" in str(patient_email):
            # Inline processing ensures network delivery succeeds on mobile and web viewports
            send_email(patient_email, subject, message)

    flash("Appointment rejected.")
    conn.close()
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
    conn = sqlite3.connect(DATABASE, timeout=20)
    cur = conn.cursor()

    cur.execute("""
        SELECT requested_date, COUNT(*) FROM appointments
        WHERE status != 'rejected' AND doctor_id=?
        GROUP BY requested_date
    """, (doctor_id,))
    data = cur.fetchall()
    conn.close()

    events = []
    for row in data:
        events.append({
            "title": f"{row[1]} appointments",
            "start": row[0],
            "color": "green" if row[1] <= 2 else "orange" if row[1] <= 5 else "red"
        })
    return jsonify(events)

# ---------------- APPOINTMENTS BY DATE ----------------
@app.route("/appointments_by_date")
def appointments_by_date():
    if not is_logged_in() or session.get("role") != "admin":
        return redirect("/login")

    date = request.args.get("date")
    doctor_id = session.get("doctor_id")

    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT p.name, p.phone, a.status
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        WHERE a.requested_date = ? AND a.status != 'rejected' AND a.doctor_id = ?
    """, (date, doctor_id))
    rows = cur.fetchall()
    conn.close()

    return {"appointments": [{"name": r["name"], "phone": r["phone"], "status": r["status"]} for r in rows]}

# ---------------- ADD MEDICINE ----------------
@app.route("/add_medicine/<int:patient_id>", methods=["POST"])
def add_medicine(patient_id):
    medicine_name = request.form["medicine_name"]
    dosage = request.form["dosage"]
    times_per_day = request.form["times_per_day"]
    total_days = request.form["total_days"]
    quantity = request.form["quantity"]
    start_date = request.form["start_date"]

    conn = sqlite3.connect(DATABASE, timeout=20)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO medicines (patient_id, medicine_name, dosage, times_per_day, total_days, quantity, start_date, reminder_sent)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
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

    conn = sqlite3.connect(DATABASE, timeout=20)
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
    conn = sqlite3.connect(DATABASE, timeout=20)
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
        try:
            start_date = datetime.strptime(med["start_date"], "%Y-%m-%d").date()
            duration_days = int(med["total_days"]) if med["total_days"] else 0
            end_date = start_date + timedelta(days=duration_days)
            days_left = (end_date - today).days

            print(f"Background Verification Tracker: {med['medicine_name']} | Days remaining: {days_left}")

            is_reminder_sent = med["reminder_sent"] if med["reminder_sent"] is not None else 0

            if 0 <= days_left <= 3 and is_reminder_sent == 0:
                subject = "Prescription Course Concluding Soon"
                message = f"Hello {med['patient_name']},\n\nThis is an automated reminder that your prescribed course for '{med['medicine_name']}' will conclude in {days_left} day(s).\n\nPlease open your portal application dashboard to check your schedule status configuration updates.\n\nThank you,\nDigital Medical Record System"

                if med["email"] and "@" in med["email"]:
                    send_email(med["email"], subject, message)

                cur.execute("UPDATE medicines SET reminder_sent = 1 WHERE id = ?", (med["id"],))
                conn.commit()

            elif days_left < 0 and is_reminder_sent == 1:
                subject = "Prescription Medication Course Completed"
                message = f"Hello {med['patient_name']},\n\nYour prescribed treatment schedule for '{med['medicine_name']}' has officially ended.\n\nPlease stop taking this medication as directed by your schedule unless explicitly instructed otherwise by your doctor.\n\nThank you,\nDigital Medical Record System"

                if med["email"] and "@" in med["email"]:
                    send_email(med["email"], subject, message)
                
                cur.execute("UPDATE medicines SET reminder_sent = 2 WHERE id = ?", (med["id"],))
                conn.commit()

        except Exception as e:
            print(f"Error checking background execution metrics for medicine ID {med.get('id', 'Unknown')}: {e}")

    conn.close()

@app.route("/patient_auto_login/<int:patient_id>")
def patient_auto_login(patient_id):
    conn = sqlite3.connect(DATABASE, timeout=20)
    conn.row_factory = sqlite3.Row
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

@app.route("/upload_reports/<int:patient_id>", methods=["POST"])
def upload_reports(patient_id):
    files = request.files.getlist("reports[]")
    names = request.form.getlist("report_names[]")

    conn = sqlite3.connect(DATABASE, timeout=20)
    cur = conn.cursor()
    for i, file in enumerate(files):
        if file and file.filename:
            filename = file.filename
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            report_name = names[i] if i < len(names) and names[i] else filename
            cur.execute("INSERT INTO patient_reports (patient_id, report_name, file_name) VALUES (?, ?, ?)", (patient_id, report_name, filename))
    conn.commit()
    conn.close()
    flash("Reports uploaded successfully!")
    return redirect(url_for("patient_profile", id=patient_id))

# ---------------- Scheduler Configuration ----------------
def run_scheduler():
    print("🚀 Background scheduler thread initialized successfully...")
    schedule.every().day.at("09:00").do(check_medicine_refills)
    schedule.every().day.at("20:00").do(check_medicine_refills)

    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_scheduler, daemon=True).start()

if __name__ == "__main__":
    app.run(debug=True)