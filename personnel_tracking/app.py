import os
import shutil
from datetime import datetime, timedelta, date
from functools import wraps
from io import BytesIO, StringIO

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField, TimeField, TextAreaField, BooleanField, FileField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Create upload directories
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)


# ==================== MODELS ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')  # admin, hr, manager, employee
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission):
        permissions = {
            'admin': ['all'],
            'hr': ['employees', 'attendance', 'leaves', 'reports', 'settings'],
            'manager': ['team_attendance', 'team_leaves', 'schedules'],
            'employee': ['profile', 'attendance', 'leaves']
        }
        return 'all' in permissions.get(self.role, []) or permission in permissions.get(self.role, [])


class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    hire_date = db.Column(db.Date, default=date.today)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), nullable=True)
    profile_photo = db.Column(db.String(256), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    department = db.relationship('Department', backref='employees')
    position = db.relationship('Position', backref='employees')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def annual_leave_balance(self):
        years_employed = (date.today() - self.hire_date).days // 365
        return min(years_employed + 18, 30)

    @property
    def sick_leave_balance(self):
        return 14

    @property
    def personal_leave_balance(self):
        return 5


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Position(db.Model):
    __tablename__ = 'positions'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    department = db.relationship('Department', backref='positions')


class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    time_in = db.Column(db.Time, nullable=True)
    time_out = db.Column(db.Time, nullable=True)
    status = db.Column(db.String(20), default='present')  # present, late, absent
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='attendance_records')


class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    leave_type = db.Column(db.String(20), nullable=False)  # annual, sick, personal, unpaid
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='leave_requests')
    approver = db.relationship('User', backref='approved_leaves')

    @property
    def days_count(self):
        return (self.end_date - self.start_date).days + 1


class Schedule(db.Model):
    __tablename__ = 'schedules'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='schedules')


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    message = db.Column(db.Text, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='notifications')


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(64), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='audit_logs')


class Holiday(db.Model):
    __tablename__ = 'holidays'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(128), default='PersonnelHub')
    company_logo = db.Column(db.String(256), nullable=True)
    work_start_time = db.Column(db.Time, default=datetime.strptime('09:00', '%H:%M').time())
    work_end_time = db.Column(db.Time, default=datetime.strptime('18:00', '%H:%M').time())
    late_threshold_minutes = db.Column(db.Integer, default=15)


# ==================== FORMS ====================

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class EmployeeForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[Length(max=20)])
    address = TextAreaField('Address')
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    hire_date = DateField('Hire Date', validators=[Optional()])
    department_id = SelectField('Department', coerce=int, validators=[Optional()])
    position_id = SelectField('Position', coerce=int, validators=[Optional()])
    profile_photo = FileField('Profile Photo')
    submit = SubmitField('Save')


class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField('Role', choices=[
        ('admin', 'Administrator'),
        ('hr', 'Human Resources'),
        ('manager', 'Supervisor/Manager'),
        ('employee', 'Employee')
    ], validators=[DataRequired()])
    employee_id = SelectField('Employee', coerce=int, validators=[Optional()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save')


class AttendanceForm(FlaskForm):
    employee_id = SelectField('Employee', coerce=int, validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    time_in = TimeField('Time In', validators=[Optional()])
    time_out = TimeField('Time Out', validators=[Optional()])
    status = SelectField('Status', choices=[
        ('present', 'Present'),
        ('late', 'Late'),
        ('absent', 'Absent')
    ], validators=[DataRequired()])
    notes = TextAreaField('Notes')
    submit = SubmitField('Save')


class LeaveRequestForm(FlaskForm):
    leave_type = SelectField('Leave Type', choices=[
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('personal', 'Personal Leave'),
        ('unpaid', 'Unpaid Leave')
    ], validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    reason = TextAreaField('Reason')
    submit = SubmitField('Submit Request')


class ScheduleForm(FlaskForm):
    employee_id = SelectField('Employee', coerce=int, validators=[DataRequired()])
    day_of_week = SelectField('Day of Week', choices=[
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ], validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    submit = SubmitField('Save')


class DepartmentForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=64)])
    description = TextAreaField('Description')
    submit = SubmitField('Save')


class PositionForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=64)])
    description = TextAreaField('Description')
    department_id = SelectField('Department', coerce=int, validators=[Optional()])
    submit = SubmitField('Save')


class HolidayForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=128)])
    date = DateField('Date', validators=[DataRequired()])
    submit = SubmitField('Save')


class PasswordResetForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


# ==================== HELPERS ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def log_audit(action, details=None):
    log = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        details=details,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()


def create_notification(user_id, title, message):
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message
    )
    db.session.add(notification)
    db.session.commit()


def generate_employee_code():
    last_employee = Employee.query.order_by(Employee.id.desc()).first()
    if last_employee:
        num = int(last_employee.employee_code.replace('EMP', '')) + 1
        return f"EMP{num:04d}"
    return "EMP0001"


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_today_stats():
    today = date.today()
    total_employees = Employee.query.filter_by(is_active=True).count()
    
    present_count = Attendance.query.filter_by(date=today, status='present').count()
    late_count = Attendance.query.filter_by(date=today, status='late').count()
    absent_count = Attendance.query.filter_by(date=today, status='absent').count()
    
    on_leave_count = LeaveRequest.query.filter(
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date <= today,
        LeaveRequest.end_date >= today
    ).count()
    
    attendance_rate = ((present_count + late_count) / total_employees * 100) if total_employees > 0 else 0
    
    return {
        'total_employees': total_employees,
        'present': present_count,
        'late': late_count,
        'absent': absent_count,
        'on_leave': on_leave_count,
        'attendance_rate': round(attendance_rate, 1)
    }


def get_monthly_attendance_data():
    data = []
    today = date.today()
    for i in range(6):
        month = today - timedelta(days=30 * i)
        month_start = month.replace(day=1)
        if month.month == 12:
            month_end = month.replace(year=month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month.replace(month=month.month + 1, day=1) - timedelta(days=1)
        
        total_days = (month_end - month_start).days + 1
        work_days = sum(1 for d in range((month_end - month_start).days + 1) 
                       if (month_start + timedelta(days=d)).weekday() < 5)
        
        present_days = Attendance.query.filter(
            Attendance.date >= month_start,
            Attendance.date <= month_end,
            Attendance.status.in_(['present', 'late'])
        ).distinct(Attendance.employee_id).count()
        
        data.insert(0, {
            'month': month.strftime('%b %Y'),
            'present': present_days,
            'expected': work_days
        })
    return data


# ==================== AUTH ROUTES ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))
        
        if not user.is_active:
            flash('Your account has been deactivated. Contact administrator.', 'warning')
            return redirect(url_for('login'))
        
        login_user(user, remember=form.remember.data)
        log_audit('login', f'User {user.username} logged in')
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        
        return redirect(url_for('dashboard'))
    
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    log_audit('logout', f'User {current_user.username} logged out')
    logout_user()
    return redirect(url_for('login'))


# ==================== DASHBOARD ====================

@app.route('/dashboard')
@login_required
def dashboard():
    stats = get_today_stats()
    monthly_data = get_monthly_attendance_data()
    recent_attendance = Attendance.query.order_by(Attendance.created_at.desc()).limit(10).all()
    recent_notifications = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    upcoming_holidays = Holiday.query.filter(
        Holiday.date >= date.today()
    ).order_by(Holiday.date).limit(5).all()
    
    # Leave status for pie chart
    pending_leaves = LeaveRequest.query.filter_by(status='pending').count()
    approved_leaves = LeaveRequest.query.filter_by(status='approved').count()
    rejected_leaves = LeaveRequest.query.filter_by(status='rejected').count()
    
    return render_template('dashboard.html',
                         stats=stats,
                         monthly_data=monthly_data,
                         recent_attendance=recent_attendance,
                         recent_notifications=recent_notifications,
                         upcoming_holidays=upcoming_holidays,
                         pending_leaves=pending_leaves,
                         approved_leaves=approved_leaves,
                         rejected_leaves=rejected_leaves)


# ==================== EMPLOYEES ====================

@app.route('/employees')
@login_required
def employees_list():
    search = request.args.get('search', '')
    department = request.args.get('department', '')
    status = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    
    query = Employee.query
    
    if search:
        query = query.filter(
            db.or_(
                Employee.first_name.ilike(f'%{search}%'),
                Employee.last_name.ilike(f'%{search}%'),
                Employee.employee_code.ilike(f'%{search}%'),
                Employee.email.ilike(f'%{search}%')
            )
        )
    
    if department:
        query = query.filter_by(department_id=int(department))
    
    if status:
        query = query.filter_by(is_active=status == 'active')
    
    employees = query.order_by(Employee.first_name).paginate(
        page=page, per_page=app.config['ITEMS_PER_PAGE'], error_out=False
    )
    
    departments = Department.query.all()
    
    return render_template('employees/list.html',
                         employees=employees,
                         departments=departments,
                         search=search,
                         selected_department=department,
                         selected_status=status)


@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'hr')
def employees_add():
    form = EmployeeForm()
    form.department_id.choices = [(0, 'Select Department')] + \
        [(d.id, d.name) for d in Department.query.all()]
    form.position_id.choices = [(0, 'Select Position')] + \
        [(p.id, p.title) for p in Position.query.all()]
    
    if form.validate_on_submit():
        employee = Employee(
            employee_code=generate_employee_code(),
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            date_of_birth=form.date_of_birth.data,
            hire_date=form.hire_date.data or date.today(),
            department_id=form.department_id.data if form.department_id.data != 0 else None,
            position_id=form.position_id.data if form.position_id.data != 0 else None
        )
        
        if form.profile_photo.data:
            file = form.profile_photo.data
            if file and allowed_file(file.filename):
                filename = secure_filename(f"emp_{employee.employee_code}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename))
                employee.profile_photo = filename
        
        db.session.add(employee)
        db.session.commit()
        
        log_audit('employee_add', f'Added employee: {employee.full_name} ({employee.employee_code})')
        flash(f'Employee {employee.full_name} has been added successfully!', 'success')
        return redirect(url_for('employees_list'))
    
    return render_template('employees/add.html', form=form)


@app.route('/employees/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'hr')
def employees_edit(id):
    employee = Employee.query.get_or_404(id)
    form = EmployeeForm(obj=employee)
    form.department_id.choices = [(0, 'Select Department')] + \
        [(d.id, d.name) for d in Department.query.all()]
    form.position_id.choices = [(0, 'Select Position')] + \
        [(p.id, p.title) for p in Position.query.all()]
    
    if form.validate_on_submit():
        employee.first_name = form.first_name.data
        employee.last_name = form.last_name.data
        employee.email = form.email.data
        employee.phone = form.phone.data
        employee.address = form.address.data
        employee.date_of_birth = form.date_of_birth.data
        employee.hire_date = form.hire_date.data or employee.hire_date
        employee.department_id = form.department_id.data if form.department_id.data != 0 else None
        employee.position_id = form.position_id.data if form.position_id.data != 0 else None
        
        if form.profile_photo.data:
            file = form.profile_photo.data
            if file and allowed_file(file.filename):
                if employee.profile_photo:
                    old_file = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', employee.profile_photo)
                    if os.path.exists(old_file):
                        os.remove(old_file)
                filename = secure_filename(f"emp_{employee.employee_code}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename))
                employee.profile_photo = filename
        
        db.session.commit()
        log_audit('employee_edit', f'Updated employee: {employee.full_name} ({employee.employee_code})')
        flash(f'Employee {employee.full_name} has been updated!', 'success')
        return redirect(url_for('employees_list'))
    
    return render_template('employees/edit.html', form=form, employee=employee)


@app.route('/employees/<int:id>/profile')
@login_required
def employees_profile(id):
    employee = Employee.query.get_or_404(id)
    
    # Check permission
    if current_user.role == 'employee' and current_user.employee_id != id:
        flash('You can only view your own profile.', 'warning')
        return redirect(url_for('dashboard'))
    
    attendance = Attendance.query.filter_by(employee_id=id).order_by(Attendance.date.desc()).limit(30).all()
    leaves = LeaveRequest.query.filter_by(employee_id=id).order_by(LeaveRequest.created_at.desc()).limit(10).all()
    
    return render_template('employees/profile.html',
                         employee=employee,
                         attendance=attendance,
                         leaves=leaves)


@app.route('/employees/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def employees_delete(id):
    employee = Employee.query.get_or_404(id)
    employee.is_active = False
    db.session.commit()
    log_audit('employee_delete', f'Deactivated employee: {employee.full_name} ({employee.employee_code})')
    flash(f'Employee {employee.full_name} has been deactivated.', 'success')
    return redirect(url_for('employees_list'))


@app.route('/employees/<int:id>/toggle-status', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def employees_toggle_status(id):
    employee = Employee.query.get_or_404(id)
    employee.is_active = not employee.is_active
    db.session.commit()
    status = 'activated' if employee.is_active else 'deactivated'
    log_audit('employee_toggle', f'{status} employee: {employee.full_name}')
    flash(f'Employee {employee.full_name} has been {status}.', 'success')
    return redirect(url_for('employees_list'))


# ==================== ATTENDANCE ====================

@app.route('/attendance')
@login_required
def attendance_list():
    search = request.args.get('search', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    status = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    
    query = Attendance.query
    
    if current_user.role == 'employee':
        query = query.filter_by(employee_id=current_user.employee_id)
    
    if search:
        query = query.join(Employee).filter(
            db.or_(
                Employee.first_name.ilike(f'%{search}%'),
                Employee.last_name.ilike(f'%{search}%'),
                Employee.employee_code.ilike(f'%{search}%')
            )
        )
    
    if date_from:
        query = query.filter(Attendance.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
    
    if date_to:
        query = query.filter(Attendance.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
    
    if status:
        query = query.filter_by(status=status)
    
    attendance_records = query.order_by(Attendance.date.desc(), Attendance.time_in.desc()).paginate(
        page=page, per_page=app.config['ITEMS_PER_PAGE'], error_out=False
    )
    
    return render_template('attendance/index.html',
                         attendance_records=attendance_records,
                         search=search,
                         date_from=date_from,
                         date_to=date_to,
                         selected_status=status)


@app.route('/attendance/time-in', methods=['POST'])
@login_required
def attendance_time_in():
    if current_user.role == 'employee' and current_user.employee_id:
        employee_id = current_user.employee_id
    else:
        employee_id = request.json.get('employee_id') if request.is_json else None
    
    if not employee_id:
        return jsonify({'success': False, 'message': 'Employee ID required'}), 400
    
    today = date.today()
    existing = Attendance.query.filter_by(
        employee_id=employee_id,
        date=today
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': 'Already timed in today'}), 400
    
    now = datetime.now()
    settings = SystemSettings.query.first()
    late_threshold = settings.late_threshold_minutes if settings else 15
    work_start = settings.work_start_time if settings else datetime.strptime('09:00', '%H:%M').time()
    
    status = 'late' if now.time().hour > work_start.hour or \
             (now.time().hour == work_start.hour and now.time().minute > late_threshold) else 'present'
    
    attendance = Attendance(
        employee_id=employee_id,
        date=today,
        time_in=now.time(),
        status=status
    )
    db.session.add(attendance)
    db.session.commit()
    
    employee = Employee.query.get(employee_id)
    log_audit('time_in', f'{employee.full_name} timed in at {now.strftime("%H:%M")}')
    
    return jsonify({
        'success': True,
        'message': f'Time in recorded at {now.strftime("%H:%M")}',
        'status': status
    })


@app.route('/attendance/time-out', methods=['POST'])
@login_required
def attendance_time_out():
    if current_user.role == 'employee' and current_user.employee_id:
        employee_id = current_user.employee_id
    else:
        employee_id = request.json.get('employee_id') if request.is_json else None
    
    if not employee_id:
        return jsonify({'success': False, 'message': 'Employee ID required'}), 400
    
    today = date.today()
    attendance = Attendance.query.filter_by(
        employee_id=employee_id,
        date=today
    ).first()
    
    if not attendance:
        return jsonify({'success': False, 'message': 'Please time in first'}), 400
    
    if attendance.time_out:
        return jsonify({'success': False, 'message': 'Already timed out today'}), 400
    
    attendance.time_out = datetime.now().time()
    db.session.commit()
    
    employee = Employee.query.get(employee_id)
    log_audit('time_out', f'{employee.full_name} timed out at {datetime.now().strftime("%H:%M")}')
    
    return jsonify({
        'success': True,
        'message': f'Time out recorded at {datetime.now().strftime("%H:%M")}'
    })


@app.route('/attendance/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'hr')
def attendance_add():
    form = AttendanceForm()
    form.employee_id.choices = [(e.id, f'{e.full_name} ({e.employee_code})') 
                                  for e in Employee.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        attendance = Attendance(
            employee_id=form.employee_id.data,
            date=form.date.data,
            time_in=form.time_in.data,
            time_out=form.time_out.data,
            status=form.status.data,
            notes=form.notes.data
        )
        db.session.add(attendance)
        db.session.commit()
        
        employee = Employee.query.get(form.employee_id.data)
        log_audit('attendance_add', f'Added attendance for {employee.full_name} on {form.date.data}')
        flash('Attendance record added successfully!', 'success')
        return redirect(url_for('attendance_list'))
    
    return render_template('attendance/add.html', form=form)


@app.route('/attendance/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'hr')
def attendance_edit(id):
    attendance = Attendance.query.get_or_404(id)
    form = AttendanceForm(obj=attendance)
    form.employee_id.choices = [(e.id, f'{e.full_name} ({e.employee_code})') 
                                  for e in Employee.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        attendance.employee_id = form.employee_id.data
        attendance.date = form.date.data
        attendance.time_in = form.time_in.data
        attendance.time_out = form.time_out.data
        attendance.status = form.status.data
        attendance.notes = form.notes.data
        db.session.commit()
        
        log_audit('attendance_edit', f'Updated attendance record ID: {id}')
        flash('Attendance record updated!', 'success')
        return redirect(url_for('attendance_list'))
    
    return render_template('attendance/edit.html', form=form, attendance=attendance)


@app.route('/attendance/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def attendance_delete(id):
    attendance = Attendance.query.get_or_404(id)
    db.session.delete(attendance)
    db.session.commit()
    log_audit('attendance_delete', f'Deleted attendance record ID: {id}')
    flash('Attendance record deleted.', 'success')
    return redirect(url_for('attendance_list'))


@app.route('/attendance/history/<int:employee_id>')
@login_required
def attendance_history(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    if current_user.role == 'employee' and current_user.employee_id != employee_id:
        flash('You can only view your own attendance history.', 'warning')
        return redirect(url_for('dashboard'))
    
    page = request.args.get('page', 1, type=int)
    attendance_records = Attendance.query.filter_by(
        employee_id=employee_id
    ).order_by(Attendance.date.desc()).paginate(
        page=page, per_page=app.config['ITEMS_PER_PAGE'], error_out=False
    )
    
    return render_template('attendance/history.html',
                         employee=employee,
                         attendance_records=attendance_records)


# ==================== LEAVES ====================

@app.route('/leaves')
@login_required
def leaves_list():
    status = request.args.get('status', '')
    leave_type = request.args.get('type', '')
    page = request.args.get('page', 1, type=int)
    
    query = LeaveRequest.query
    
    if current_user.role == 'employee':
        query = query.filter_by(employee_id=current_user.employee_id)
    
    if status:
        query = query.filter_by(status=status)
    
    if leave_type:
        query = query.filter_by(leave_type=leave_type)
    
    leaves = query.order_by(LeaveRequest.created_at.desc()).paginate(
        page=page, per_page=app.config['ITEMS_PER_PAGE'], error_out=False
    )
    
    return render_template('leaves/index.html',
                         leaves=leaves,
                         selected_status=status,
                         selected_type=leave_type)


@app.route('/leaves/apply', methods=['GET', 'POST'])
@login_required
def leaves_apply():
    if not current_user.employee_id:
        flash('You are not linked to an employee profile.', 'warning')
        return redirect(url_for('leaves_list'))
    
    form = LeaveRequestForm()
    
    if form.validate_on_submit():
        if form.end_date.data < form.start_date.data:
            flash('End date must be after start date.', 'danger')
            return render_template('leaves/apply.html', form=form)
        
        leave = LeaveRequest(
            employee_id=current_user.employee_id,
            leave_type=form.leave_type.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            reason=form.reason.data
        )
        db.session.add(leave)
        db.session.commit()
        
        # Notify HR/Admin
        hr_users = User.query.filter(User.role.in_(['admin', 'hr'])).all()
        for hr in hr_users:
            create_notification(hr.id, 'New Leave Request',
                              f'{current_user.employee.full_name} requested {leave.leave_type} leave')
        
        log_audit('leave_apply', f'Applied for {leave.leave_type} leave: {leave.start_date} to {leave.end_date}')
        flash('Leave request submitted successfully!', 'success')
        return redirect(url_for('leaves_list'))
    
    employee = Employee.query.get(current_user.employee_id)
    return render_template('leaves/apply.html', form=form, employee=employee)


@app.route('/leaves/<int:id>/approve', methods=['POST'])
@login_required
@role_required('admin', 'hr', 'manager')
def leaves_approve(id):
    leave = LeaveRequest.query.get_or_404(id)
    leave.status = 'approved'
    leave.approved_by = current_user.id
    leave.approved_at = datetime.utcnow()
    db.session.commit()
    
    create_notification(leave.employee.user_id, 'Leave Approved',
                        f'Your {leave.leave_type} leave has been approved.')
    log_audit('leave_approve', f'Approved leave ID {id} for {leave.employee.full_name}')
    flash('Leave request approved!', 'success')
    return redirect(url_for('leaves_list'))


@app.route('/leaves/<int:id>/reject', methods=['POST'])
@login_required
@role_required('admin', 'hr', 'manager')
def leaves_reject(id):
    leave = LeaveRequest.query.get_or_404(id)
    leave.status = 'rejected'
    leave.approved_by = current_user.id
    leave.approved_at = datetime.utcnow()
    db.session.commit()
    
    create_notification(leave.employee.user_id, 'Leave Rejected',
                        f'Your {leave.leave_type} leave has been rejected.')
    log_audit('leave_reject', f'Rejected leave ID {id} for {leave.employee.full_name}')
    flash('Leave request rejected.', 'success')
    return redirect(url_for('leaves_list'))


# ==================== SCHEDULES ====================

@app.route('/schedules')
@login_required
def schedules_list():
    employee_id = request.args.get('employee_id', type=int)
    day_of_week = request.args.get('day_of_week', type=int)
    
    query = Schedule.query
    
    if current_user.role == 'employee':
        query = query.filter_by(employee_id=current_user.employee_id)
    elif employee_id:
        query = query.filter_by(employee_id=employee_id)
    
    if day_of_week is not None:
        query = query.filter_by(day_of_week=day_of_week)
    
    schedules = query.order_by(Schedule.day_of_week, Schedule.start_time).all()
    employees = Employee.query.filter_by(is_active=True).all()
    
    return render_template('schedules/index.html',
                         schedules=schedules,
                         employees=employees,
                         selected_employee=employee_id,
                         selected_day=day_of_week)


@app.route('/schedules/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'hr', 'manager')
def schedules_add():
    form = ScheduleForm()
    form.employee_id.choices = [(e.id, f'{e.full_name} ({e.employee_code})') 
                                  for e in Employee.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        # Check if schedule already exists
        existing = Schedule.query.filter_by(
            employee_id=form.employee_id.data,
            day_of_week=form.day_of_week.data
        ).first()
        
        if existing:
            existing.start_time = form.start_time.data
            existing.end_time = form.end_time.data
            flash('Schedule updated!', 'success')
        else:
            schedule = Schedule(
                employee_id=form.employee_id.data,
                day_of_week=form.day_of_week.data,
                start_time=form.start_time.data,
                end_time=form.end_time.data
            )
            db.session.add(schedule)
            flash('Schedule added!', 'success')
        
        db.session.commit()
        log_audit('schedule_add', f'Added schedule for employee ID {form.employee_id.data}')
        return redirect(url_for('schedules_list'))
    
    return render_template('schedules/add.html', form=form)


@app.route('/schedules/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'hr', 'manager')
def schedules_delete(id):
    schedule = Schedule.query.get_or_404(id)
    db.session.delete(schedule)
    db.session.commit()
    log_audit('schedule_delete', f'Deleted schedule ID {id}')
    flash('Schedule deleted.', 'success')
    return redirect(url_for('schedules_list'))


# ==================== REPORTS ====================

@app.route('/reports')
@login_required
@role_required('admin', 'hr')
def reports_list():
    report_type = request.args.get('type', 'attendance')
    date_from = request.args.get('date_from', (date.today() - timedelta(days=30)).isoformat())
    date_to = request.args.get('date_to', date.today().isoformat())
    
    return render_template('reports/index.html',
                         report_type=report_type,
                         date_from=date_from,
                         date_to=date_to)


@app.route('/reports/attendance')
@login_required
@role_required('admin', 'hr')
def report_attendance():
    date_from = request.args.get('date_from', (date.today() - timedelta(days=30)).isoformat())
    date_to = request.args.get('date_to', date.today().isoformat())
    
    records = Attendance.query.filter(
        Attendance.date >= datetime.strptime(date_from, '%Y-%m-%d').date(),
        Attendance.date <= datetime.strptime(date_to, '%Y-%m-%d').date()
    ).all()
    
    summary = {
        'total': len(records),
        'present': len([r for r in records if r.status == 'present']),
        'late': len([r for r in records if r.status == 'late']),
        'absent': len([r for r in records if r.status == 'absent'])
    }
    
    return jsonify({'records': [{
        'employee': r.employee.full_name,
        'employee_code': r.employee.employee_code,
        'date': r.date.strftime('%Y-%m-%d'),
        'time_in': r.time_in.strftime('%H:%M') if r.time_in else '-',
        'time_out': r.time_out.strftime('%H:%M') if r.time_out else '-',
        'status': r.status
    } for r in records], 'summary': summary})


@app.route('/reports/export/<format>')
@login_required
@role_required('admin', 'hr')
def export_report(format):
    date_from = request.args.get('date_from', (date.today() - timedelta(days=30)).isoformat())
    date_to = request.args.get('date_to', date.today().isoformat())
    report_type = request.args.get('type', 'attendance')
    
    records = Attendance.query.filter(
        Attendance.date >= datetime.strptime(date_from, '%Y-%m-%d').date(),
        Attendance.date <= datetime.strptime(date_to, '%Y-%m-%d').date()
    ).all()
    
    data = [{
        'Employee Code': r.employee.employee_code,
        'Employee Name': r.employee.full_name,
        'Date': r.date.strftime('%Y-%m-%d'),
        'Time In': r.time_in.strftime('%H:%M') if r.time_in else '-',
        'Time Out': r.time_out.strftime('%H:%M') if r.time_out else '-',
        'Status': r.status.capitalize()
    } for r in records]
    
    if format == 'csv':
        output = StringIO()
        if data:
            output.write(','.join(data[0].keys()) + '\n')
            for row in data:
                output.write(','.join(str(v) for v in row.values()) + '\n')
        
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'attendance_report_{date_from}_{date_to}.csv'
        )
    
    elif format == 'excel':
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = 'Attendance Report'
        
        if data:
            ws.append(list(data[0].keys()))
            for row in data:
                ws.append(list(row.values()))
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'attendance_report_{date_from}_{date_to}.xlsx'
        )
    
    elif format == 'pdf':
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph('Attendance Report', styles['Title']))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f'Period: {date_from} to {date_to}', styles['Normal']))
        elements.append(Spacer(1, 12))
        
        if data:
            table_data = [list(data[0].keys())]
            for row in data:
                table_data.append(list(row.values()))
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
        
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'attendance_report_{date_from}_{date_to}.pdf'
        )
    
    return redirect(url_for('reports_list'))


# ==================== NOTIFICATIONS ====================

@app.route('/notifications')
@login_required
def notifications_list():
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).paginate(
        page=request.args.get('page', 1, type=int),
        per_page=app.config['ITEMS_PER_PAGE'],
        error_out=False
    )
    return render_template('notifications/index.html', notifications=notifications)


@app.route('/notifications/<int:id>/read', methods=['POST'])
@login_required
def notifications_read(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return jsonify({'success': True})


@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def notifications_mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


# ==================== USERS ====================

@app.route('/users')
@login_required
@role_required('admin')
def users_list():
    search = request.args.get('search', '')
    role = request.args.get('role', '')
    page = request.args.get('page', 1, type=int)
    
    query = User.query
    
    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    if role:
        query = query.filter_by(role=role)
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=app.config['ITEMS_PER_PAGE'], error_out=False
    )
    
    return render_template('users/list.html', users=users, search=search, selected_role=role)


@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def users_add():
    form = UserForm()
    form.employee_id.choices = [(0, 'No Employee Link')] + \
        [(e.id, f'{e.full_name} ({e.employee_code})') 
         for e in Employee.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists!', 'danger')
            return render_template('users/add.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already exists!', 'danger')
            return render_template('users/add.html', form=form)
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
            employee_id=form.employee_id.data if form.employee_id.data != 0 else None,
            is_active=form.is_active.data
        )
        user.set_password('password123')  # Default password
        db.session.add(user)
        db.session.commit()
        
        log_audit('user_add', f'Added user: {user.username} with role {user.role}')
        flash(f'User {user.username} created! Default password: password123', 'success')
        return redirect(url_for('users_list'))
    
    return render_template('users/add.html', form=form)


@app.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def users_edit(id):
    user = User.query.get_or_404(id)
    form = UserForm(obj=user)
    form.employee_id.choices = [(0, 'No Employee Link')] + \
        [(e.id, f'{e.full_name} ({e.employee_code})') 
         for e in Employee.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        user.employee_id = form.employee_id.data if form.employee_id.data != 0 else None
        user.is_active = form.is_active.data
        db.session.commit()
        
        log_audit('user_edit', f'Updated user: {user.username}')
        flash(f'User {user.username} updated!', 'success')
        return redirect(url_for('users_list'))
    
    return render_template('users/edit.html', form=form, user=user)


@app.route('/users/<int:id>/reset-password', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def users_reset_password(id):
    user = User.query.get_or_404(id)
    form = PasswordResetForm()
    
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        log_audit('password_reset', f'Reset password for user: {user.username}')
        flash(f'Password for {user.username} has been reset!', 'success')
        return redirect(url_for('users_list'))
    
    return render_template('users/reset_password.html', form=form, user=user)


@app.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def users_delete(id):
    if id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('users_list'))
    
    user = User.query.get_or_404(id)
    log_audit('user_delete', f'Deleted user: {user.username}')
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} deleted.', 'success')
    return redirect(url_for('users_list'))


# ==================== SETTINGS ====================

@app.route('/settings')
@login_required
@role_required('admin', 'hr')
def settings_index():
    settings = SystemSettings.query.first()
    if not settings:
        settings = SystemSettings(company_name='PersonnelHub')
        db.session.add(settings)
        db.session.commit()
    
    return render_template('settings/index.html', settings=settings)


@app.route('/settings/save', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def settings_save():
    settings = SystemSettings.query.first()
    if not settings:
        settings = SystemSettings()
        db.session.add(settings)
    
    settings.company_name = request.form.get('company_name', 'PersonnelHub')
    settings.work_start_time = datetime.strptime(
        request.form.get('work_start_time', '09:00'), '%H:%M'
    ).time()
    settings.work_end_time = datetime.strptime(
        request.form.get('work_end_time', '18:00'), '%H:%M'
    ).time()
    settings.late_threshold_minutes = int(request.form.get('late_threshold_minutes', 15))
    
    db.session.commit()
    log_audit('settings_update', 'System settings updated')
    flash('Settings saved successfully!', 'success')
    return redirect(url_for('settings_index'))


@app.route('/settings/departments')
@login_required
@role_required('admin', 'hr')
def departments_list():
    departments = Department.query.order_by(Department.name).all()
    return render_template('settings/departments.html', departments=departments)


@app.route('/settings/departments/add', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def departments_add():
    form = DepartmentForm()
    if form.validate_on_submit():
        dept = Department(
            name=form.name.data,
            description=form.description.data
        )
        db.session.add(dept)
        db.session.commit()
        log_audit('department_add', f'Added department: {dept.name}')
        flash(f'Department {dept.name} added!', 'success')
    return redirect(url_for('departments_list'))


@app.route('/settings/departments/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def departments_delete(id):
    dept = Department.query.get_or_404(id)
    if dept.employees:
        flash('Cannot delete department with employees!', 'danger')
        return redirect(url_for('departments_list'))
    log_audit('department_delete', f'Deleted department: {dept.name}')
    db.session.delete(dept)
    db.session.commit()
    flash('Department deleted.', 'success')
    return redirect(url_for('departments_list'))


@app.route('/settings/positions')
@login_required
@role_required('admin', 'hr')
def positions_list():
    positions = Position.query.all()
    departments = Department.query.order_by(Department.name).all()
    return render_template('settings/positions.html', positions=positions, departments=departments)


@app.route('/settings/positions/add', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def positions_add():
    form = PositionForm()
    if form.validate_on_submit():
        pos = Position(
            title=form.title.data,
            description=form.description.data,
            department_id=form.department_id.data if form.department_id.data != 0 else None
        )
        db.session.add(pos)
        db.session.commit()
        log_audit('position_add', f'Added position: {pos.title}')
        flash(f'Position {pos.title} added!', 'success')
    return redirect(url_for('positions_list'))


@app.route('/settings/positions/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def positions_delete(id):
    pos = Position.query.get_or_404(id)
    if pos.employees:
        flash('Cannot delete position with employees!', 'danger')
        return redirect(url_for('positions_list'))
    log_audit('position_delete', f'Deleted position: {pos.title}')
    db.session.delete(pos)
    db.session.commit()
    flash('Position deleted.', 'success')
    return redirect(url_for('positions_list'))


@app.route('/settings/holidays')
@login_required
@role_required('admin', 'hr')
def holidays_list():
    holidays = Holiday.query.order_by(Holiday.date).all()
    return render_template('settings/holidays.html', holidays=holidays)


@app.route('/settings/holidays/add', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def holidays_add():
    form = HolidayForm()
    if form.validate_on_submit():
        holiday = Holiday(
            name=form.name.data,
            date=form.date.data
        )
        db.session.add(holiday)
        db.session.commit()
        log_audit('holiday_add', f'Added holiday: {holiday.name}')
        flash(f'Holiday {holiday.name} added!', 'success')
    return redirect(url_for('holidays_list'))


@app.route('/settings/holidays/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'hr')
def holidays_delete(id):
    holiday = Holiday.query.get_or_404(id)
    log_audit('holiday_delete', f'Deleted holiday: {holiday.name}')
    db.session.delete(holiday)
    db.session.commit()
    flash('Holiday deleted.', 'success')
    return redirect(url_for('holidays_list'))


# ==================== AUDIT LOGS ====================

@app.route('/audit-logs')
@login_required
@role_required('admin')
def audit_logs():
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)
    
    query = AuditLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if action:
        query = query.filter(AuditLog.action.ilike(f'%{action}%'))
    
    if date_from:
        query = query.filter(AuditLog.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
    
    if date_to:
        query = query.filter(AuditLog.created_at <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    
    logs = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=app.config['ITEMS_PER_PAGE'], error_out=False
    )
    
    users = User.query.all()
    
    return render_template('audit_logs.html',
                         logs=logs,
                         users=users,
                         selected_user=user_id,
                         selected_action=action,
                         date_from=date_from,
                         date_to=date_to)


# ==================== BACKUP/RESTORE ====================

@app.route('/settings/backup')
@login_required
@role_required('admin')
def backup_database():
    backup_dir = os.path.join(basedir, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'backup_{timestamp}.db')
    
    shutil.copy2(os.path.join(basedir, 'instance', 'personnel.db'), backup_file)
    
    log_audit('backup', f'Database backed up: {backup_file}')
    flash(f'Database backed up successfully!', 'success')
    
    return send_file(
        backup_file,
        as_attachment=True,
        download_name=f'personnel_backup_{timestamp}.db'
    )


@app.route('/settings/restore', methods=['POST'])
@login_required
@role_required('admin')
def restore_database():
    if 'backup_file' not in request.files:
        flash('No file selected!', 'danger')
        return redirect(url_for('settings_index'))
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('No file selected!', 'danger')
        return redirect(url_for('settings_index'))
    
    if file and file.filename.endswith('.db'):
        db_path = os.path.join(basedir, 'instance', 'personnel.db')
        file.save(db_path)
        log_audit('restore', 'Database restored')
        flash('Database restored successfully! Please log in again.', 'success')
        return redirect(url_for('logout'))
    
    flash('Invalid file format!', 'danger')
    return redirect(url_for('settings_index'))


# ==================== API ENDPOINTS ====================

@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    return jsonify(get_today_stats())


@app.route('/api/employees/search')
@login_required
def api_employees_search():
    query = request.args.get('q', '')
    employees = Employee.query.filter(
        db.or_(
            Employee.first_name.ilike(f'%{query}%'),
            Employee.last_name.ilike(f'%{query}%'),
            Employee.employee_code.ilike(f'%{query}%')
        ),
        Employee.is_active == True
    ).limit(10).all()
    
    return jsonify([{
        'id': e.id,
        'text': f'{e.full_name} ({e.employee_code})'
    } for e in employees])


@app.route('/api/notifications/count')
@login_required
def api_notifications_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


# ==================== JINJA FILTERS ====================

@app.template_filter('datetime')
def format_datetime(value):
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime('%b %d, %Y %H:%M')
    return value

@app.context_processor
def inject_now():
    return {
        'now': datetime.now(),
        'today': date.today(),
        'current_year': date.today().year
    }


# ==================== INITIALIZATION ====================

def init_database():
    """Initialize database with default data"""
    db.create_all()
    
    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@personnelhub.com',
            role='admin',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
    
    # Create HR user if not exists
    if not User.query.filter_by(username='hr').first():
        hr = User(
            username='hr',
            email='hr@personnelhub.com',
            role='hr',
            is_active=True
        )
        hr.set_password('hr123')
        db.session.add(hr)
    
    # Create default departments
    if Department.query.count() == 0:
        departments = [
            Department(name='Administration', description='Administrative tasks'),
            Department(name='Human Resources', description='HR and recruitment'),
            Department(name='Information Technology', description='IT and software development'),
            Department(name='Finance', description='Finance and accounting'),
            Department(name='Marketing', description='Marketing and sales')
        ]
        for dept in departments:
            db.session.add(dept)
    
    # Create default positions
    if Position.query.count() == 0:
        positions = [
            Position(title='Manager', department_id=1),
            Position(title='Team Lead', department_id=3),
            Position(title='Software Engineer', department_id=3),
            Position(title='Accountant', department_id=4),
            Position(title='Marketing Specialist', department_id=5)
        ]
        for pos in positions:
            db.session.add(pos)
    
    # Create system settings
    if not SystemSettings.query.first():
        settings = SystemSettings(
            company_name='PersonnelHub',
            work_start_time=datetime.strptime('09:00', '%H:%M').time(),
            work_end_time=datetime.strptime('18:00', '%H:%M').time(),
            late_threshold_minutes=15
        )
        db.session.add(settings)
    
    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
