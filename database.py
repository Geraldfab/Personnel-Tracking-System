import sqlite3
import os
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'personnel.db')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'avatars')
QR_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'qrcodes')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Ensure upload directories exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(QR_UPLOAD_DIR, exist_ok=True)

    conn = get_db()
    cursor = conn.cursor()

    # Admin Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT DEFAULT 'Administrator',
        created_at TEXT NOT NULL
    )
    ''')

    # Schedules table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        work_days TEXT DEFAULT 'Mon-Fri',
        description TEXT
    )
    ''')

    # Employee table (with biometric_enrolled flag and schedule_id)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_code TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        department TEXT NOT NULL,
        role TEXT NOT NULL,
        status TEXT DEFAULT 'In Office',
        location_name TEXT DEFAULT 'Headquarters - Main IT Lab',
        latitude REAL DEFAULT 37.7749,
        longitude REAL DEFAULT -122.4194,
        avatar_url TEXT,
        join_date TEXT,
        last_checkin TEXT,
        bio TEXT,
        biometric_enrolled INTEGER DEFAULT 1,
        schedule_id INTEGER DEFAULT 1,
        FOREIGN KEY (schedule_id) REFERENCES schedules (id)
    )
    ''')

    # Attendance log table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER NOT NULL,
        check_in_time TEXT NOT NULL,
        check_out_time TEXT,
        status TEXT NOT NULL,
        location_name TEXT,
        latitude REAL,
        longitude REAL,
        notes TEXT,
        verification_method TEXT DEFAULT 'QR Code Scanner',
        FOREIGN KEY (emp_id) REFERENCES employees (id)
    )
    ''')

    # Migration checks for existing databases
    cursor.execute("PRAGMA table_info(employees)")
    emp_columns = [row['name'] for row in cursor.fetchall()]
    if 'biometric_enrolled' not in emp_columns:
        cursor.execute("ALTER TABLE employees ADD COLUMN biometric_enrolled INTEGER DEFAULT 1")
    if 'schedule_id' not in emp_columns:
        cursor.execute("ALTER TABLE employees ADD COLUMN schedule_id INTEGER DEFAULT 1")

    cursor.execute("PRAGMA table_info(attendance_logs)")
    log_columns = [row['name'] for row in cursor.fetchall()]
    if 'verification_method' not in log_columns:
        cursor.execute("ALTER TABLE attendance_logs ADD COLUMN verification_method TEXT DEFAULT 'QR Code Scanner'")

    # Leave requests table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id INTEGER NOT NULL,
        leave_type TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        reason TEXT,
        status TEXT DEFAULT 'Pending',
        created_at TEXT NOT NULL,
        FOREIGN KEY (emp_id) REFERENCES employees (id)
    )
    ''')

    conn.commit()
    conn.close()

    # Seed initial admin and employees
    seed_data_if_empty()

def seed_data_if_empty():
    conn = get_db()
    cursor = conn.cursor()

    # Seed Schedules if empty
    cursor.execute("SELECT COUNT(*) FROM schedules")
    sched_count = cursor.fetchone()[0]
    if sched_count == 0:
        default_schedules = [
            ("Regular Day Shift", "08:00", "17:00", "Mon-Fri", "Standard 8 AM to 5 PM office hours"),
            ("Night Shift Operations", "22:00", "07:00", "Mon-Fri", "Overnight server & SOC monitoring shift"),
            ("Flexible WFH Shift", "09:00", "18:00", "Mon-Fri", "Remote engineering flexible hours"),
            ("24/7 Security Rotation", "00:00", "23:59", "Rotational", "Continuous cybersecurity desk monitoring")
        ]
        cursor.executemany('''
        INSERT INTO schedules (name, start_time, end_time, work_days, description)
        VALUES (?, ?, ?, ?, ?)
        ''', default_schedules)

    # Seed Admin if empty
    cursor.execute("SELECT COUNT(*) FROM admin_users")
    admin_count = cursor.fetchone()[0]
    if admin_count == 0:
        default_admin_pass = generate_password_hash("admin123")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute('''
        INSERT INTO admin_users (username, password_hash, full_name, email, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', ("admin", default_admin_pass, "System Administrator", "admin@techcore.io", "Lead IT Director", now_str))

    # Seed Employees if empty
    cursor.execute("SELECT COUNT(*) FROM employees")
    emp_count = cursor.fetchone()[0]

    if emp_count == 0:
        sample_employees = [
            ("IT-1001", "Alexander Wright", "alex.wright@techcore.io", "+1 (555) 234-5678", "DevOps & Infrastructure", "Lead DevOps Engineer", "In Office", "HQ Data Center - Floor 4", 37.7749, -122.4194, "/static/uploads/avatars/avatar_0f27b562f2.jpg", "2021-03-15", datetime.now().strftime("%Y-%m-%d %H:%M"), "Specialized in Kubernetes clusters, CI/CD automation, and AWS cloud management.", 1),
            ("IT-1002", "Elena Rostova", "elena.r@techcore.io", "+1 (555) 876-5432", "Software Engineering", "Senior Full-Stack Architect", "In Office", "Software Lab A", 37.7749, -122.4194, "/static/uploads/avatars/avatar_123baa0e6c.jpg", "2020-11-01", datetime.now().strftime("%Y-%m-%d %H:%M"), "Core architect for enterprise web platforms, Python microservices, and React apps.", 1),
            ("IT-1003", "Marcus Vance", "m.vance@techcore.io", "+1 (555) 345-6789", "Cybersecurity", "Cyber Threat Analyst", "Remote", "Home Office (San Jose, CA)", 37.3382, -121.8863, "/static/uploads/avatars/avatar_9bcb597850.jpg", "2022-01-20", datetime.now().strftime("%Y-%m-%d %H:%M"), "Penetration testing expert, SIEM monitoring, SOC incident management.", 1),
            ("IT-1004", "Sophia Chen", "sophia.chen@techcore.io", "+1 (555) 987-6543", "Cloud & Data", "Cloud Solutions Engineer", "In Meeting", "Conference Room Cyber 3", 37.7749, -122.4194, "/static/uploads/avatars/avatar_9e22cda7d9.jpg", "2022-06-10", datetime.now().strftime("%Y-%m-%d %H:%M"), "Architecting multi-cloud Azure & GCP enterprise infrastructure.", 1),
            ("IT-1005", "David Kalu", "david.kalu@techcore.io", "+1 (555) 456-7890", "IT Support & Ops", "Systems Administrator", "In Office", "Helpdesk Desk 12", 37.7749, -122.4194, "/static/uploads/avatars/avatar_cd61292125.jpg", "2023-02-14", datetime.now().strftime("%Y-%m-%d %H:%M"), "Hardware deployment, Active Directory, network configuration, end-user support.", 1),
            ("IT-1006", "Chloe Bennett", "chloe.b@techcore.io", "+1 (555) 654-3210", "Software Engineering", "Frontend Lead / UI Engineer", "Remote", "Co-Working Space (Oakland)", 37.8044, -122.2712, "/static/uploads/avatars/avatar_e3aa1d8129.jpg", "2021-08-05", datetime.now().strftime("%Y-%m-%d %H:%M"), "Crafting fluid mobile UX, design systems, and responsive web applications.", 1),
            ("IT-1007", "Liam O'Connor", "liam.oc@techcore.io", "+1 (555) 789-0123", "QA & Testing", "Automation Test Lead", "On Leave", "Annual Medical Leave", 37.7749, -122.4194, "/static/uploads/avatars/avatar_35df343371.jpg", "2022-09-12", datetime.now().strftime("%Y-%m-%d %H:%M"), "End-to-end Selenium/Playwright automation pipelines and performance benchmarking.", 1),
            ("IT-1008", "Aisha Patel", "aisha.p@techcore.io", "+1 (555) 890-1234", "Product & Management", "IT Operations Director", "In Office", "Executive Suite 501", 37.7749, -122.4194, "/static/uploads/avatars/avatar_ecde6475b5.jpg", "2019-05-18", datetime.now().strftime("%Y-%m-%d %H:%M"), "Leading IT strategy, vendor management, budget planning, and team scaling.", 1)
        ]

        cursor.executemany('''
        INSERT INTO employees (emp_code, full_name, email, phone, department, role, status, location_name, latitude, longitude, avatar_url, join_date, last_checkin, bio, biometric_enrolled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_employees)

        # Seed attendance logs
        now = datetime.now()
        logs = [
            (1, (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"), None, "In Office", "HQ Data Center - Floor 4", 37.7749, -122.4194, "Server rack maintenance check-in", "Face Biometrics"),
            (2, (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M"), None, "In Office", "Software Lab A", 37.7749, -122.4194, "Sprint release review", "Face Biometrics"),
            (3, (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M"), None, "Remote", "Home Office (San Jose, CA)", 37.3382, -121.8863, "Logged in via Secure VPN", "Manual"),
            (4, (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"), None, "In Meeting", "Conference Room Cyber 3", 37.7749, -122.4194, "Client Security Audit sync", "Manual"),
            (5, (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M"), None, "In Office", "Helpdesk Desk 12", 37.7749, -122.4194, "Morning queue triage", "Face Biometrics"),
            (6, (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"), None, "Remote", "Co-Working Space (Oakland)", 37.8044, -122.2712, "Design review prep", "Manual")
        ]

        cursor.executemany('''
        INSERT INTO attendance_logs (emp_id, check_in_time, check_out_time, status, location_name, latitude, longitude, notes, verification_method)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', logs)

        # Seed leave requests
        today = date.today()
        leaves = [
            (7, "Sick Leave", today.strftime("%Y-%m-%d"), (today + timedelta(days=2)).strftime("%Y-%m-%d"), "Medical procedure recovery", "Approved", (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")),
            (3, "Remote Day", (today + timedelta(days=3)).strftime("%Y-%m-%d"), (today + timedelta(days=4)).strftime("%Y-%m-%d"), "ISP maintenance at residence", "Pending", now.strftime("%Y-%m-%d %H:%M")),
            (6, "Vacation", (today + timedelta(days=10)).strftime("%Y-%m-%d"), (today + timedelta(days=14)).strftime("%Y-%m-%d"), "Annual leave & conference attendance", "Pending", (now - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"))
        ]

        cursor.executemany('''
        INSERT INTO leave_requests (emp_id, leave_type, start_date, end_date, reason, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', leaves)

    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, args)
    rv = cursor.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, args)
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def generate_qr_code_file(emp_code):
    import qrcode
    os.makedirs(QR_UPLOAD_DIR, exist_ok=True)
    filename = f"qr_{emp_code}.png"
    filepath = os.path.join(QR_UPLOAD_DIR, filename)

    if not os.path.exists(filepath):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(emp_code)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0b0f19", back_color="#ffffff")
        img.save(filepath)

    return f"/static/uploads/qrcodes/{filename}"

def generate_default_avatar_file(emp_code, full_name):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"avatar_default_{emp_code}.svg"
    filepath = os.path.join(UPLOAD_DIR, filename)

    # Extract initials
    parts = (full_name or '').strip().split()
    initials = "".join([p[0].upper() for p in parts[:2]]) if parts else "TC"

    # Gradients based on emp_code
    colors = [
        ("#06b6d4", "#3b82f6"),
        ("#10b981", "#06b6d4"),
        ("#8b5cf6", "#6366f1"),
        ("#f59e0b", "#ef4444"),
        ("#ec4899", "#8b5cf6"),
        ("#0284c7", "#0f172a")
    ]
    idx = sum(ord(c) for c in emp_code) % len(colors)
    c1, c2 = colors[idx]

    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="120" height="120">
  <defs>
    <linearGradient id="grad_{emp_code}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c1}" />
      <stop offset="100%" stop-color="{c2}" />
    </linearGradient>
  </defs>
  <rect width="120" height="120" rx="26" fill="#0b0f19" stroke="url(#grad_{emp_code})" stroke-width="3" />
  <circle cx="60" cy="60" r="42" fill="url(#grad_{emp_code})" opacity="0.25" />
  <text x="60" y="68" font-family="'Inter', -apple-system, sans-serif" font-size="34" font-weight="800" fill="#ffffff" text-anchor="middle" dominant-baseline="middle">{initials}</text>
</svg>'''
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(svg_content)

    return f"/static/uploads/avatars/{filename}"


