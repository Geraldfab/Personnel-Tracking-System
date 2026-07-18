// ===== Sidebar Toggle =====
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('show');
}

// ===== Notification Dropdown =====
function toggleNotifications() {
    const menu = document.getElementById('notificationMenu');
    menu.classList.toggle('show');
    
    // Close on click outside
    document.addEventListener('click', function closeMenu(e) {
        if (!e.target.closest('.notification-dropdown')) {
            menu.classList.remove('show');
            document.removeEventListener('click', closeMenu);
        }
    });
}

// ===== Mark All Notifications Read =====
function markAllRead() {
    fetch('/notifications/mark-all-read', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        }
    });
}

// ===== Initialize Tooltips =====
document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
    
    // Add active class to current nav link
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(function(link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});

// ===== Format Date =====
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// ===== Format Time =====
function formatTime(timeString) {
    if (!timeString) return '-';
    const [hours, minutes] = timeString.split(':');
    return `${hours}:${minutes}`;
}

// ===== Show Toast =====
function showToast(type, message) {
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        <span>${message}</span>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===== Confirm Delete =====
function confirmDelete(message = 'Are you sure you want to delete this item?') {
    return confirm(message);
}

// ===== Search Functionality =====
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ===== Export Functions =====
function exportToPDF() {
    window.location.href = '/reports/export/pdf?' + new URLSearchParams(window.location.search);
}

function exportToExcel() {
    window.location.href = '/reports/export/excel?' + new URLSearchParams(window.location.search);
}

function exportToCSV() {
    window.location.href = '/reports/export/csv?' + new URLSearchParams(window.location.search);
}

// ===== Chart Initialization Helpers =====
function initBarChart(ctx, labels, data, label, color) {
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                backgroundColor: color,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function initLineChart(ctx, labels, datasets) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function initPieChart(ctx, labels, data, colors) {
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// ===== Form Validation =====
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// ===== API Helpers =====
async function fetchAPI(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast('error', 'An error occurred. Please try again.');
        throw error;
    }
}

// ===== Time In/Out Functions =====
async function timeIn(employeeId = null) {
    const body = employeeId ? { employee_id: employeeId } : {};
    
    try {
        const data = await fetchAPI('/attendance/time-in', {
            method: 'POST',
            body: JSON.stringify(body)
        });
        
        if (data.success) {
            showToast('success', data.message);
            setTimeout(() => location.reload(), 1500);
        } else {
            showToast('error', data.message);
        }
    } catch (error) {
        // Error already handled by fetchAPI
    }
}

async function timeOut(employeeId = null) {
    const body = employeeId ? { employee_id: employeeId } : {};
    
    try {
        const data = await fetchAPI('/attendance/time-out', {
            method: 'POST',
            body: JSON.stringify(body)
        });
        
        if (data.success) {
            showToast('success', data.message);
            setTimeout(() => location.reload(), 1500);
        } else {
            showToast('error', data.message);
        }
    } catch (error) {
        // Error already handled by fetchAPI
    }
}

// ===== Notification Bell Animation =====
function pulseNotification() {
    const bell = document.querySelector('.notification-btn i');
    if (bell) {
        bell.classList.add('fa-beat');
        setTimeout(() => bell.classList.remove('fa-beat'), 1000);
    }
}

// Poll for new notifications every 30 seconds
setInterval(() => {
    fetch('/api/notifications/count')
        .then(response => response.json())
        .then(data => {
            const count = data.count;
            const badge = document.querySelector('.notification-count');
            const bell = document.querySelector('.notification-btn');
            
            if (badge) {
                if (count > 0) {
                    badge.textContent = count;
                    badge.style.display = 'block';
                    pulseNotification();
                } else {
                    badge.style.display = 'none';
                }
            }
        })
        .catch(() => {});
}, 30000);

// ===== Print Function =====
function printPage() {
    window.print();
}

// ===== Password Visibility Toggle =====
function togglePasswordVisibility(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fas fa-eye';
    }
}
