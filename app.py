from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import database as db
from datetime import datetime, date
import os
import uuid
from io import BytesIO

# ReportLab PDF Imports
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)
app.secret_key = 'techcore_personnel_tracking_secret_key_v2'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize SQLite Database
with app.app_context():
    db.init_db()

@app.context_processor
def inject_admin_status():
    return {
        'is_admin': session.get('is_admin', False),
        'admin_name': session.get('admin_name', 'Guest'),
        'admin_role': session.get('admin_role', 'Viewer')
    }

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('is_admin'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        admin = db.query_db("SELECT * FROM admin_users WHERE username = ?", [username], one=True)
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['is_admin'] = True
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['full_name']
            session['admin_role'] = admin['role']
            flash(f"Welcome back, {admin['full_name']}! Signed in as Administrator.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid administrator username or password.", "danger")

    return render_template('login.html', active_page='login')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out of the Administrator session.", "info")
    return redirect(url_for('dashboard'))

# Views
@app.route('/')
def dashboard():
    total_staff = db.query_db("SELECT COUNT(*) as count FROM employees", one=True)['count']
    in_office = db.query_db("SELECT COUNT(*) as count FROM employees WHERE status = 'In Office'", one=True)['count']
    remote = db.query_db("SELECT COUNT(*) as count FROM employees WHERE status = 'Remote'", one=True)['count']
    on_leave = db.query_db("SELECT COUNT(*) as count FROM employees WHERE status = 'On Leave'", one=True)['count']

    recent_checkins = db.query_db('''
        SELECT a.*, e.full_name, e.role, e.department, e.avatar_url, e.emp_code
        FROM attendance_logs a
        JOIN employees e ON a.emp_id = e.id
        ORDER BY a.id DESC LIMIT 6
    ''')

    dept_stats = db.query_db('''
        SELECT department, COUNT(*) as count,
        SUM(CASE WHEN status = 'In Office' THEN 1 ELSE 0 END) as active_office,
        SUM(CASE WHEN status = 'Remote' THEN 1 ELSE 0 END) as active_remote
        FROM employees GROUP BY department
    ''')

    all_employees = db.query_db("SELECT id, full_name, emp_code, status, role, avatar_url FROM employees ORDER BY full_name COLLATE NOCASE ASC")

    return render_template('dashboard.html',
                           total_staff=total_staff,
                           in_office=in_office,
                           remote=remote,
                           on_leave=on_leave,
                           recent_checkins=recent_checkins,
                           dept_stats=dept_stats,
                           all_employees=all_employees,
                           active_page='dashboard')

@app.route('/personnel')
def personnel():
    dept_filter = request.args.get('department', '').strip()
    status_filter = request.args.get('status', '').strip()
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'code_asc').strip()

    query = '''
        SELECT e.*, s.name as schedule_name
        FROM employees e
        LEFT JOIN schedules s ON e.schedule_id = s.id
        WHERE 1=1
    '''
    params = []

    if dept_filter:
        query += " AND e.department = ?"
        params.append(dept_filter)
    if status_filter:
        query += " AND e.status = ?"
        params.append(status_filter)
    if search_query:
        query += " AND (e.full_name LIKE ? OR e.emp_code LIKE ? OR e.role LIKE ? OR e.email LIKE ? OR e.location_name LIKE ?)"
        term = f"%{search_query}%"
        params.extend([term, term, term, term, term])

    # Dynamic Organized Sorting
    if sort_by == 'name_asc':
        query += " ORDER BY e.full_name COLLATE NOCASE ASC"
    elif sort_by == 'name_desc':
        query += " ORDER BY e.full_name COLLATE NOCASE DESC"
    elif sort_by == 'dept_asc':
        query += " ORDER BY e.department COLLATE NOCASE ASC, e.full_name COLLATE NOCASE ASC"
    elif sort_by == 'status':
        query += " ORDER BY e.status ASC, e.full_name COLLATE NOCASE ASC"
    else:  # default code_asc
        query += " ORDER BY CAST(SUBSTR(e.emp_code, 4) AS INTEGER) ASC, e.id ASC"

    employees = db.query_db(query, params)

    # Summary workforce metrics
    total_count = db.query_db("SELECT COUNT(*) as count FROM employees", one=True)['count']
    in_office_count = db.query_db("SELECT COUNT(*) as count FROM employees WHERE status IN ('In Office', 'In Office (Late)')", one=True)['count']
    late_count = db.query_db("SELECT COUNT(*) as count FROM employees WHERE status = 'In Office (Late)'", one=True)['count']
    remote_count = db.query_db("SELECT COUNT(*) as count FROM employees WHERE status = 'Remote'", one=True)['count']
    meeting_count = db.query_db("SELECT COUNT(*) as count FROM employees WHERE status = 'In Meeting'", one=True)['count']
    leave_count = db.query_db("SELECT COUNT(*) as count FROM employees WHERE status = 'On Leave'", one=True)['count']

    departments = db.query_db("SELECT DISTINCT department FROM employees ORDER BY department")
    schedules = db.query_db("SELECT id, name, start_time, end_time FROM schedules ORDER BY id ASC")
    statuses = ['In Office', 'In Office (Late)', 'Remote', 'In Meeting', 'On Leave', 'Out of Office']

    return render_template('personnel.html',
                           employees=employees,
                           departments=departments,
                           statuses=statuses,
                           schedules=schedules,
                           selected_dept=dept_filter,
                           selected_status=status_filter,
                           search_query=search_query,
                           sort_by=sort_by,
                           total_count=total_count,
                           in_office_count=in_office_count,
                           late_count=late_count,
                           remote_count=remote_count,
                           meeting_count=meeting_count,
                           leave_count=leave_count,
                           active_page='personnel')

@app.route('/personnel/<int:emp_id>')
def employee_detail(emp_id):
    emp = db.query_db('''
        SELECT e.*, s.name as schedule_name, s.start_time, s.end_time, s.work_days
        FROM employees e
        LEFT JOIN schedules s ON e.schedule_id = s.id
        WHERE e.id = ?
    ''', [emp_id], one=True)

    if not emp:
        flash("Employee record not found.", "danger")
        return redirect(url_for('personnel'))

    logs = db.query_db("SELECT * FROM attendance_logs WHERE emp_id = ? ORDER BY id DESC LIMIT 15", [emp_id])
    leaves = db.query_db("SELECT * FROM leave_requests WHERE emp_id = ? ORDER BY id DESC LIMIT 10", [emp_id])

    # Ensure QR Code generated
    qr_url = db.generate_qr_code_file(emp['emp_code'])

    return render_template('employee_detail.html', emp=emp, logs=logs, leaves=leaves, qr_url=qr_url, active_page='personnel')

# Digital ID Card View Endpoint
@app.route('/personnel/<int:emp_id>/id-card')
def employee_id_card(emp_id):
    emp = db.query_db('''
        SELECT e.*, s.name as schedule_name, s.start_time, s.end_time
        FROM employees e
        LEFT JOIN schedules s ON e.schedule_id = s.id
        WHERE e.id = ?
    ''', [emp_id], one=True)
    
    if not emp:
        flash("Employee record not found.", "danger")
        return redirect(url_for('personnel'))

    qr_url = db.generate_qr_code_file(emp['emp_code'])
    return render_template('id_card_modal.html', emp=emp, qr_url=qr_url)

@app.route('/attendance')
def attendance():
    logs = db.query_db('''
        SELECT a.*, e.full_name, e.role, e.department, e.avatar_url, e.emp_code
        FROM attendance_logs a
        JOIN employees e ON a.emp_id = e.id
        ORDER BY a.id DESC LIMIT 35
    ''')
    all_employees = db.query_db("SELECT id, full_name, emp_code, status, avatar_url FROM employees ORDER BY full_name COLLATE NOCASE ASC")

    return render_template('attendance.html', logs=logs, all_employees=all_employees, active_page='attendance')

@app.route('/leaves')
def leaves():
    pending_leaves = db.query_db('''
        SELECT l.*, e.full_name, e.role, e.department, e.avatar_url, e.emp_code
        FROM leave_requests l
        JOIN employees e ON l.emp_id = e.id
        WHERE l.status = 'Pending'
        ORDER BY l.id DESC
    ''')
    history_leaves = db.query_db('''
        SELECT l.*, e.full_name, e.role, e.department, e.avatar_url, e.emp_code
        FROM leave_requests l
        JOIN employees e ON l.emp_id = e.id
        WHERE l.status != 'Pending'
        ORDER BY l.id DESC LIMIT 20
    ''')
    all_employees = db.query_db("SELECT id, full_name, emp_code FROM employees ORDER BY full_name COLLATE NOCASE ASC")

    return render_template('leaves.html',
                           pending_leaves=pending_leaves,
                           history_leaves=history_leaves,
                           all_employees=all_employees,
                           active_page='leaves')

# Schedules Management View
@app.route('/schedules')
def schedules():
    sched_list = db.query_db("SELECT * FROM schedules ORDER BY id")
    employees_by_schedule = db.query_db('''
        SELECT e.id, e.full_name, e.emp_code, e.role, e.department, e.avatar_url, e.status, s.name as schedule_name, s.start_time, s.end_time, s.id as sched_id
        FROM employees e
        LEFT JOIN schedules s ON e.schedule_id = s.id
        ORDER BY e.full_name COLLATE NOCASE ASC
    ''')
    all_employees = db.query_db("SELECT id, full_name, emp_code, role FROM employees ORDER BY full_name COLLATE NOCASE ASC")

    return render_template('schedules.html',
                           schedules=sched_list,
                           employees=employees_by_schedule,
                           all_employees=all_employees,
                           active_page='schedules')

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

@app.route('/settings')
def settings():
    return render_template('settings.html', active_page='settings', local_ip=get_local_ip())

# Helper to evaluate Attendance-In timing (8:00 AM - 9:00 AM window)
def evaluate_checkin_timing(now_dt=None):
    if not now_dt:
        now_dt = datetime.now()
    
    hour = now_dt.hour
    minute = now_dt.minute
    time_formatted = now_dt.strftime("%I:%M %p")

    # Standard Attendance-In Window: 8:00 AM to 9:00 AM
    # If arriving after 09:00 AM (e.g. 09:01 AM or later) -> LATE
    if (hour > 9) or (hour == 9 and minute > 0):
        is_late = True
        status_note = f"Late Arrival (Checked in at {time_formatted})"
        lateness_tag = " [LATE]"
    else:
        is_late = False
        status_note = f"On-Time Arrival (Checked in at {time_formatted})"
        lateness_tag = ""

    return is_late, status_note, lateness_tag

# API Endpoints

@app.route('/api/check-in', methods=['POST'])
def api_check_in():
    data = request.get_json() or request.form
    emp_id = data.get('emp_id')
    mode = data.get('mode', 'check_in') # 'check_in' or 'check_out'
    status = data.get('status', 'In Office')
    location_name = data.get('location_name', 'Mobile Check-in')
    lat = data.get('latitude', 37.7749)
    lng = data.get('longitude', -122.4194)
    notes_custom = data.get('notes', '')
    verification_method = data.get('verification_method', 'Manual')

    if not emp_id:
        return jsonify({'success': False, 'message': 'Employee selection required'}), 400

    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")

    emp = db.query_db("SELECT full_name FROM employees WHERE id = ?", [emp_id], one=True)
    name = emp['full_name'] if emp else 'Employee'

    if mode == 'check_out' or now_dt.hour >= 16:
        status = 'Out of Office'
        notes = f"Attendance-Out at {now_dt.strftime('%I:%M %p')}"
        if now_dt.hour >= 16:
            notes += " (4:00 PM Shift End)"
        if notes_custom:
            notes += f" - {notes_custom}"

        db.execute_db('''
            UPDATE employees
            SET status = ?, location_name = ?, last_checkin = ?
            WHERE id = ?
        ''', [status, location_name, now_str, emp_id])

        latest_log = db.query_db("SELECT id FROM attendance_logs WHERE emp_id = ? AND check_out_time IS NULL ORDER BY id DESC LIMIT 1", [emp_id], one=True)
        if latest_log:
            db.execute_db("UPDATE attendance_logs SET check_out_time = ?, notes = notes || ? WHERE id = ?", [now_str, f" | {notes}", latest_log['id']])
            log_id = latest_log['id']
        else:
            log_id = db.execute_db('''
                INSERT INTO attendance_logs (emp_id, check_in_time, check_out_time, status, location_name, latitude, longitude, notes, verification_method)
                VALUES (?, ?, ?, 'Out of Office', ?, ?, ?, ?, ?)
            ''', [emp_id, now_str, now_str, location_name, lat, lng, notes, verification_method])

        return jsonify({
            'success': True,
            'message': f'Attendance-Out confirmed for {name} at {now_dt.strftime("%I:%M %p")}',
            'last_checkin': now_str,
            'log_id': log_id
        })
    else:
        is_late, time_note, lateness_tag = evaluate_checkin_timing(now_dt)
        if is_late:
            status = 'In Office (Late)'
        
        notes = f"{time_note}"
        if notes_custom:
            notes += f" - {notes_custom}"

        db.execute_db('''
            UPDATE employees
            SET status = ?, location_name = ?, latitude = ?, longitude = ?, last_checkin = ?
            WHERE id = ?
        ''', [status, location_name, lat, lng, now_str, emp_id])

        log_id = db.execute_db('''
            INSERT INTO attendance_logs (emp_id, check_in_time, status, location_name, latitude, longitude, notes, verification_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [emp_id, now_str, status, location_name, lat, lng, notes, verification_method])

        return jsonify({
            'success': True,
            'message': f'Attendance-In verified for {name} ({status}) at {now_dt.strftime("%I:%M %p")}',
            'last_checkin': now_str,
            'log_id': log_id
        })

# QR Code Camera Recognition API Endpoint (Smart In/Out detection)
@app.route('/api/qr-scan', methods=['POST'])
def api_qr_scan():
    data = request.get_json() or {}
    qr_data = (data.get('qr_data') or data.get('emp_code') or '').strip()
    location_name = data.get('location_name', 'QR Code Scanner (HQ Gate)')
    lat = data.get('latitude', 37.7749)
    lng = data.get('longitude', -122.4194)

    if not qr_data:
        return jsonify({'success': False, 'message': 'No QR Code data detected'}), 400

    emp = db.query_db("SELECT * FROM employees WHERE emp_code = ? OR id = ?", [qr_data, qr_data], one=True)
    if not emp:
        return jsonify({'success': False, 'message': f'No employee found matching code "{qr_data}"'}), 404

    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")

    # Smart 4:00 PM Attendance-Out Check:
    if now_dt.hour >= 16 and emp['status'] in ['In Office', 'In Office (Late)', 'In Meeting']:
        status = 'Out of Office'
        notes = f"Attendance-Out (4:00 PM Shift End) at {now_dt.strftime('%I:%M %p')}"

        db.execute_db('''
            UPDATE employees
            SET status = ?, location_name = ?, last_checkin = ?
            WHERE id = ?
        ''', [status, location_name, now_str, emp['id']])

        latest_log = db.query_db("SELECT id FROM attendance_logs WHERE emp_id = ? AND check_out_time IS NULL ORDER BY id DESC LIMIT 1", [emp['id']], one=True)
        if latest_log:
            db.execute_db("UPDATE attendance_logs SET check_out_time = ?, notes = notes || ? WHERE id = ?", [now_str, f" | {notes}", latest_log['id']])
        else:
            db.execute_db('''
                INSERT INTO attendance_logs (emp_id, check_in_time, check_out_time, status, location_name, latitude, longitude, notes, verification_method)
                VALUES (?, ?, ?, 'Out of Office', ?, ?, ?, ?, 'QR Code Scanner')
            ''', [emp['id'], now_str, now_str, location_name, lat, lng, notes])

        return jsonify({
            'success': True,
            'employee_name': emp['full_name'],
            'emp_code': emp['emp_code'],
            'role': emp['role'],
            'status': status,
            'avatar_url': emp['avatar_url'],
            'message': f'Attendance-Out Confirmed! {emp["full_name"]} checked out.',
            'timestamp': now_str
        })
    else:
        is_late, time_note, lateness_tag = evaluate_checkin_timing(now_dt)
        status = 'In Office (Late)' if is_late else 'In Office'
        notes = f"{time_note} - Scanned Digital ID Card"

        db.execute_db('''
            UPDATE employees
            SET status = ?, location_name = ?, latitude = ?, longitude = ?, last_checkin = ?
            WHERE id = ?
        ''', [status, location_name, lat, lng, now_str, emp['id']])

        db.execute_db('''
            INSERT INTO attendance_logs (emp_id, check_in_time, status, location_name, latitude, longitude, notes, verification_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'QR Code Scanner')
        ''', [emp['id'], now_str, status, location_name, lat, lng, notes])

        return jsonify({
            'success': True,
            'employee_name': emp['full_name'],
            'emp_code': emp['emp_code'],
            'role': emp['role'],
            'status': status,
            'avatar_url': emp['avatar_url'],
            'message': f'QR Code Verified! {emp["full_name"]} ({status}).',
            'timestamp': now_str
        })

# Attendance-Out API Endpoint (Individual Check-Out)
@app.route('/api/check-out', methods=['POST'])
def api_check_out():
    data = request.get_json() or request.form
    emp_id = data.get('emp_id')
    emp_code = data.get('emp_code')
    location_name = data.get('location_name', 'HQ Main Exit')
    lat = data.get('latitude', 37.7749)
    lng = data.get('longitude', -122.4194)

    if not emp_id and emp_code:
        emp_obj = db.query_db("SELECT id FROM employees WHERE emp_code = ?", [emp_code], one=True)
        if emp_obj:
            emp_id = emp_obj['id']

    if not emp_id:
        return jsonify({'success': False, 'message': 'Employee selection required for Check-Out'}), 400

    emp = db.query_db("SELECT full_name, emp_code FROM employees WHERE id = ?", [emp_id], one=True)
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404

    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")

    db.execute_db('''
        UPDATE employees
        SET status = 'Out of Office', location_name = ?, last_checkin = ?
        WHERE id = ?
    ''', [location_name, now_str, emp_id])

    notes_text = f"Attendance-Out logged at {now_dt.strftime('%I:%M %p')}"
    if now_dt.hour >= 16:
        notes_text += " (4:00 PM Shift End)"

    latest_log = db.query_db("SELECT id FROM attendance_logs WHERE emp_id = ? AND check_out_time IS NULL ORDER BY id DESC LIMIT 1", [emp_id], one=True)
    if latest_log:
        db.execute_db("UPDATE attendance_logs SET check_out_time = ?, notes = notes || ? WHERE id = ?", [now_str, f" | {notes_text}", latest_log['id']])
    else:
        db.execute_db('''
            INSERT INTO attendance_logs (emp_id, check_in_time, check_out_time, status, location_name, latitude, longitude, notes, verification_method)
            VALUES (?, ?, ?, 'Out of Office', ?, ?, ?, ?, 'Attendance-Out')
        ''', [emp_id, now_str, now_str, location_name, lat, lng, notes_text])

    return jsonify({
        'success': True,
        'employee_name': emp['full_name'],
        'emp_code': emp['emp_code'],
        'message': f'Attendance-Out confirmed for {emp["full_name"]} at {now_dt.strftime("%I:%M %p")}',
        'timestamp': now_str
    })

# 4:00 PM Batch Attendance-Out Action (Shift End Trigger)
@app.route('/api/check-out/batch-4pm', methods=['POST'])
def api_batch_4pm_checkout():
    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")

    active_employees = db.query_db("SELECT id, full_name, emp_code FROM employees WHERE status IN ('In Office', 'In Office (Late)', 'In Meeting')")

    count = 0
    for emp in active_employees:
        db.execute_db("UPDATE employees SET status = 'Out of Office', last_checkin = ? WHERE id = ?", [now_str, emp['id']])
        latest_log = db.query_db("SELECT id FROM attendance_logs WHERE emp_id = ? AND check_out_time IS NULL ORDER BY id DESC LIMIT 1", [emp['id']], one=True)
        if latest_log:
            db.execute_db("UPDATE attendance_logs SET check_out_time = ?, notes = notes || ' | 4:00 PM Shift End Auto Checkout' WHERE id = ?", [now_str, latest_log['id']])
        count += 1

    flash(f"Executed 4:00 PM Attendance-Out for {count} active personnel!", "success")
    return redirect(url_for('dashboard'))

# Add Employee Endpoint
@app.route('/api/employee/add', methods=['POST'])
def api_add_employee():
    if not session.get('is_admin'):
        flash("Administrator login required to register new personnel.", "danger")
        return redirect(url_for('login'))

    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    department = request.form.get('department')
    role = request.form.get('role')
    status = request.form.get('status', 'In Office')
    schedule_id = request.form.get('schedule_id', 1)
    location_name = request.form.get('location_name', 'Headquarters Main Office')
    bio = request.form.get('bio', '')
    avatar_url = request.form.get('avatar_url', '')

    if not full_name or not email or not department or not role:
        flash("Please fill in all required fields (Name, Email, Department, Role).", "warning")
        return redirect(url_for('personnel'))

    # Handle Profile Photo File Upload
    file = request.files.get('avatar_file')
    if file and file.filename != '' and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"avatar_{uuid.uuid4().hex[:10]}.{ext}"
        save_path = os.path.join(db.UPLOAD_DIR, unique_filename)
        file.save(save_path)
        avatar_url = url_for('static', filename=f'uploads/avatars/{unique_filename}')

    # Generate collision-free unique employee code
    max_id = db.query_db("SELECT COALESCE(MAX(id), 0) as max_id FROM employees", one=True)['max_id']
    emp_code = f"IT-{1001 + max_id}"
    while db.query_db("SELECT id FROM employees WHERE emp_code = ?", [emp_code], one=True):
        max_id += 1
        emp_code = f"IT-{1001 + max_id}"

    if not avatar_url:
        avatar_url = db.generate_default_avatar_file(emp_code, full_name)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    join_date = date.today().strftime("%Y-%m-%d")

    db.execute_db('''
        INSERT INTO employees (emp_code, full_name, email, phone, department, role, status, location_name, avatar_url, join_date, last_checkin, bio, biometric_enrolled, schedule_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    ''', [emp_code, full_name, email, phone, department, role, status, location_name, avatar_url, join_date, now_str, bio, schedule_id])

    # Auto-generate QR code image for new employee
    db.generate_qr_code_file(emp_code)

    flash(f"Successfully registered new personnel {full_name} ({emp_code}) and generated Digital ID QR code!", "success")
    return redirect(url_for('personnel'))

# Delete Employee Endpoint (Admin Only)
@app.route('/api/employee/delete/<int:emp_id>', methods=['POST'])
def api_delete_employee(emp_id):
    if not session.get('is_admin'):
        flash("Administrator privileges required to remove personnel.", "danger")
        return redirect(url_for('personnel'))

    emp = db.query_db("SELECT full_name, emp_code FROM employees WHERE id = ?", [emp_id], one=True)
    if not emp:
        flash("Employee record not found.", "danger")
        return redirect(url_for('personnel'))

    db.execute_db("DELETE FROM attendance_logs WHERE emp_id = ?", [emp_id])
    db.execute_db("DELETE FROM leave_requests WHERE emp_id = ?", [emp_id])
    db.execute_db("DELETE FROM employees WHERE id = ?", [emp_id])

    flash(f"Personnel record {emp['full_name']} ({emp['emp_code']}) permanently deleted.", "success")
    return redirect(url_for('personnel'))

# Schedule APIs
@app.route('/api/schedule/add', methods=['POST'])
def api_add_schedule():
    if not session.get('is_admin'):
        flash("Administrator login required to create work shifts.", "danger")
        return redirect(url_for('schedules'))

    name = request.form.get('name')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    work_days = request.form.get('work_days', 'Mon-Fri')
    description = request.form.get('description', '')

    if not name or not start_time or not end_time:
        flash("Shift Name, Start Time, and End Time are required.", "warning")
        return redirect(url_for('schedules'))

    db.execute_db('''
        INSERT INTO schedules (name, start_time, end_time, work_days, description)
        VALUES (?, ?, ?, ?, ?)
    ''', [name, start_time, end_time, work_days, description])

    flash(f"Work shift '{name}' created successfully!", "success")
    return redirect(url_for('schedules'))

@app.route('/api/schedule/assign', methods=['POST'])
def api_assign_schedule():
    if not session.get('is_admin'):
        flash("Administrator privileges required to assign work schedules.", "danger")
        return redirect(url_for('schedules'))

    emp_id = request.form.get('emp_id')
    schedule_id = request.form.get('schedule_id')

    if not emp_id or not schedule_id:
        flash("Select employee and work shift.", "warning")
        return redirect(url_for('schedules'))

    db.execute_db("UPDATE employees SET schedule_id = ? WHERE id = ?", [schedule_id, emp_id])
    flash("Work schedule assigned successfully!", "success")
    return redirect(url_for('schedules'))

@app.route('/api/leave/request', methods=['POST'])
def api_leave_request():
    data = request.form
    emp_id = data.get('emp_id')
    leave_type = data.get('leave_type')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    reason = data.get('reason')

    if not emp_id or not leave_type or not start_date or not end_date:
        flash("Missing required leave request fields.", "warning")
        return redirect(url_for('leaves'))

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    db.execute_db('''
        INSERT INTO leave_requests (emp_id, leave_type, start_date, end_date, reason, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'Pending', ?)
    ''', [emp_id, leave_type, start_date, end_date, reason, created_at])

    flash("Leave request submitted successfully for manager approval!", "success")
    return redirect(url_for('leaves'))

@app.route('/api/leave/action', methods=['POST'])
def api_leave_action():
    if not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Administrator privileges required for approval/rejection.'}), 403

    data = request.get_json() or request.form
    leave_id = data.get('leave_id')
    action = data.get('action')

    if not leave_id or action not in ['Approved', 'Rejected']:
        return jsonify({'success': False, 'message': 'Invalid request parameters'}), 400

    leave = db.query_db("SELECT * FROM leave_requests WHERE id = ?", [leave_id], one=True)
    if not leave:
        return jsonify({'success': False, 'message': 'Leave request not found'}), 404

    db.execute_db("UPDATE leave_requests SET status = ? WHERE id = ?", [action, leave_id])

    if action == 'Approved':
        today_str = date.today().strftime("%Y-%m-%d")
        if leave['start_date'] <= today_str <= leave['end_date']:
            db.execute_db("UPDATE employees SET status = 'On Leave' WHERE id = ?", [leave['emp_id']])

    return jsonify({'success': True, 'message': f'Leave request successfully marked as {action}'})

# PDF Export Route 1: Attendance Logs Report
@app.route('/export/pdf/attendance')
def export_attendance_pdf():
    logs = db.query_db('''
        SELECT a.*, e.full_name, e.emp_code, e.department, e.role
        FROM attendance_logs a
        JOIN employees e ON a.emp_id = e.id
        ORDER BY a.id DESC LIMIT 100
    ''')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0B0F19'),
        spaceAfter=6
    )
    sub_style = ParagraphStyle(
        'ReportSub',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=15
    )

    elements.append(Paragraph("TECHCORE IT - ATTENDANCE & LOCATION LOG REPORT", title_style))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &bull; Total Logs: {len(logs)}", sub_style))

    table_data = [["Emp Code", "Personnel Name", "Department", "Status", "Location Node", "Verification", "Timestamp"]]
    for log in logs:
        table_data.append([
            log['emp_code'],
            log['full_name'],
            log['department'],
            log['status'],
            (log['location_name'][:24] + '...') if log['location_name'] and len(log['location_name']) > 24 else (log['location_name'] or '-'),
            log['verification_method'] or 'QR Code Scanner',
            log['check_in_time']
        ])

    t = Table(table_data, colWidths=[65, 110, 100, 65, 95, 75, 75])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0B0F19')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#06B6D4')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    elements.append(t)

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'Attendance_Report_{date.today()}.pdf')

# PDF Export Route 2: Personnel Roster Report
@app.route('/export/pdf/personnel')
def export_personnel_pdf():
    employees = db.query_db('''
        SELECT e.*, s.name as schedule_name
        FROM employees e
        LEFT JOIN schedules s ON e.schedule_id = s.id
        ORDER BY e.full_name COLLATE NOCASE ASC
    ''')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0B0F19'),
        spaceAfter=6
    )
    sub_style = ParagraphStyle(
        'ReportSub',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=15
    )

    elements.append(Paragraph("TECHCORE IT - PERSONNEL ROSTER REPORT", title_style))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &bull; Total Headcount: {len(employees)}", sub_style))

    table_data = [["Code", "Full Name", "Role", "Department", "Contact Phone", "Status", "Work Shift"]]
    for emp in employees:
        table_data.append([
            emp['emp_code'],
            emp['full_name'],
            emp['role'][:20],
            emp['department'][:18],
            emp['phone'],
            emp['status'],
            emp['schedule_name'] or 'Standard Day'
        ])

    t = Table(table_data, colWidths=[55, 110, 100, 95, 80, 65, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0B0F19')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#06B6D4')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    elements.append(t)

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'Personnel_Roster_{date.today()}.pdf')

@app.route('/api/reset-db', methods=['POST'])
def api_reset_db():
    if not session.get('is_admin'):
        flash("Administrator privileges required to reset system database.", "danger")
        return redirect(url_for('settings'))

    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.init_db()
    flash("Database successfully reset and re-seeded with IT sample workforce, schedules & admin credentials!", "success")
    return redirect(url_for('settings'))

if __name__ == '__main__':
    local_ip = get_local_ip()
    print("=" * 70)
    print("   TECHCORE IT PERSONNEL TRACKING SYSTEM (100% OFFLINE READY)")
    print("=" * 70)
    print(f" * Local PC Access:          http://127.0.0.1:5000")
    print(f" * Local Network / Hotspot:  http://{local_ip}:5000")
    print("-" * 70)
    print(" [Presentation Offline Mode]:")
    print(" * All assets (FontAwesome, HTML5-QRCode, Fonts, Avatars) are local.")
    print(" * To connect an Android device or second PC without internet:")
    print("   Connect both devices to the same local Wi-Fi or Mobile Hotspot,")
    print(f"   then open: http://{local_ip}:5000 in the mobile browser.")
    print("=" * 70)
    app.run(host='0.0.0.0', port=5000, debug=True)
