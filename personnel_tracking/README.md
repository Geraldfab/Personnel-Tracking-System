# PersonnelHub - Personnel Tracking System

A comprehensive employee management and attendance tracking system built with Python Flask.

## Features

### Core Features
- **Employee Management**: Add, edit, view, and manage employee profiles
- **Attendance Tracking**: Time in/out, daily attendance, status tracking
- **Leave Management**: Request, approve, and reject leave applications
- **Schedule Management**: Create and assign work schedules
- **Reports & Analytics**: Generate attendance reports with export options
- **Notifications**: Real-time notifications for important updates
- **User Management**: Role-based access control (Admin, HR, Manager, Employee)
- **Audit Logs**: Track all system activities
- **Backup & Restore**: Database backup and restore functionality

### User Roles
1. **Administrator**: Full system access
2. **Human Resources (HR)**: Employee management, attendance, leaves, reports
3. **Supervisor/Manager**: Team management, schedule, leave approval
4. **Employee**: View profile, clock in/out, request leaves

## Installation

### Prerequisites
- Python 3.9+
- pip

### Setup

1. **Clone the repository**
   ```bash
   cd personnel_tracking
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access the application**
   - Open your browser and go to: `http://localhost:5000`

## Default Credentials

| Role  | Username | Password   |
|-------|----------|------------|
| Admin | admin    | admin123   |
| HR    | hr       | hr123      |

## Project Structure

```
personnel_tracking/
├── app.py                 # Main application
├── config.py              # Configuration
├── requirements.txt       # Dependencies
├── static/
│   ├── css/styles.css    # Styles
│   ├── js/main.js        # JavaScript
│   └── uploads/          # Uploaded files
├── templates/             # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── employees/
│   ├── attendance/
│   ├── leaves/
│   ├── schedules/
│   ├── reports/
│   ├── notifications/
│   ├── users/
│   └── settings/
└── instance/
    └── personnel.db       # SQLite database
```

## API Endpoints

### Authentication
- `POST /login` - User login
- `GET /logout` - User logout

### Employees
- `GET /employees` - List employees
- `POST /employees/add` - Add employee
- `GET /employees/<id>/profile` - View profile
- `POST /employees/<id>/edit` - Edit employee
- `POST /employees/<id>/delete` - Delete employee

### Attendance
- `GET /attendance` - List attendance records
- `POST /attendance/time-in` - Time in
- `POST /attendance/time-out` - Time out
- `GET /attendance/history/<id>` - View history

### Leaves
- `GET /leaves` - List leave requests
- `POST /leaves/apply` - Apply for leave
- `POST /leaves/<id>/approve` - Approve leave
- `POST /leaves/<id>/reject` - Reject leave

### Reports
- `GET /reports` - View reports
- `GET /reports/export/<format>` - Export (pdf/excel/csv)

## Technologies Used

- **Backend**: Python Flask
- **Database**: SQLite (production: PostgreSQL)
- **Frontend**: HTML5, CSS3, JavaScript
- **UI Framework**: Bootstrap 5
- **Charts**: Chart.js
- **Icons**: Font Awesome 6
- **Authentication**: Flask-Login

## Security Features

- Password hashing (Werkzeug)
- CSRF protection
- Session management
- Role-based access control
- Input validation
- SQL injection prevention

## Screenshots

### Dashboard
![Dashboard](docs/dashboard.png)

### Employee List
![Employees](docs/employees.png)

### Attendance
![Attendance](docs/attendance.png)

## License

This project is licensed under the MIT License.

## Support

For support, email support@personnelhub.com or create an issue.
