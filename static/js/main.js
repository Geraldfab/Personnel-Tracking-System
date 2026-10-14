// IT Personnel Tracking System - Mobile & Interactivity JS

document.addEventListener('DOMContentLoaded', () => {
    // Theme setup from localStorage
    const savedTheme = localStorage.getItem('techcore_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    // Initialize quick location check if available
    initLocationHelper();
});

// Theme Switcher
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem('techcore_theme', nextTheme);
    updateThemeIcon(nextTheme);
    showToast(`Switched to ${nextTheme.toUpperCase()} theme mode.`, 'info');
}

function updateThemeIcon(theme) {
    const themeBtn = document.getElementById('themeToggleBtn');
    if (themeBtn) {
        themeBtn.innerHTML = theme === 'dark' 
            ? '<i class="fa-solid fa-sun text-warning"></i>' 
            : '<i class="fa-solid fa-moon text-info"></i>';
        themeBtn.setAttribute('title', theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode');
    }
}

// Modal Helpers
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Geolocation helper for Android/Mobile device check-in
function getDeviceLocation(targetLatId, targetLngId, targetLocNameId) {
    const statusText = document.getElementById('geoStatusText');
    if (statusText) statusText.innerText = "Acquiring Android GPS...";

    if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;

                if (document.getElementById(targetLatId)) document.getElementById(targetLatId).value = lat.toFixed(5);
                if (document.getElementById(targetLngId)) document.getElementById(targetLngId).value = lng.toFixed(5);
                
                // Fetch reverse geocoding or fallback label
                if (document.getElementById(targetLocNameId)) {
                    document.getElementById(targetLocNameId).value = `Mobile GPS (${lat.toFixed(3)}, ${lng.toFixed(3)})`;
                }

                if (statusText) {
                    statusText.innerHTML = '<span class="text-success"><i class="fa-solid fa-check-circle"></i> GPS Location Acquired</span>';
                }
                showToast("GPS coordinates updated!", "success");
            },
            (error) => {
                console.warn("Geolocation fallback:", error.message);
                if (statusText) {
                    statusText.innerHTML = '<span class="text-muted"><i class="fa-solid fa-location-dot"></i> Using default HQ coordinates</span>';
                }
            },
            { timeout: 10000, enableHighAccuracy: true }
        );
    } else {
        if (statusText) statusText.innerText = "Geolocation not supported, using default HQ location.";
    }
}

function initLocationHelper() {
    // Auto-setup location triggers if check-in modal present
}

// Submit Check-in via AJAX
async function submitQuickCheckin(event) {
    event.preventDefault();
    const form = event.target;
    const empId = form.emp_id.value;
    const status = form.status.value;
    const locationName = form.location_name.value;
    const lat = form.latitude ? form.latitude.value : 37.7749;
    const lng = form.longitude ? form.longitude.value : -122.4194;
    const notes = form.notes ? form.notes.value : '';

    if (!empId) {
        showToast("Please select an employee.", "warning");
        return;
    }

    try {
        const response = await fetch('/api/check-in', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                emp_id: empId,
                status: status,
                location_name: locationName,
                latitude: lat,
                longitude: lng,
                notes: notes
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            closeModal('checkinModal');
            setTimeout(() => {
                window.location.reload();
            }, 800);
        } else {
            showToast(result.message || "Failed to update status", "danger");
        }
    } catch (err) {
        console.error(err);
        showToast("Network error updating status", "danger");
    }
}

// Action for Leave Requests (Approve / Reject)
async function handleLeaveAction(leaveId, action) {
    if (!confirm(`Are you sure you want to set this leave request to ${action}?`)) return;

    try {
        const response = await fetch('/api/leave/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ leave_id: leaveId, action: action })
        });

        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => window.location.reload(), 600);
        } else {
            showToast(result.message, "danger");
        }
    } catch (err) {
        console.error(err);
        showToast("Error executing leave action.", "danger");
    }
}

// Toast System
function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    
    let iconClass = 'fa-circle-info text-info';
    if (type === 'success') iconClass = 'fa-circle-check text-success';
    if (type === 'danger') iconClass = 'fa-triangle-exclamation text-danger';
    if (type === 'warning') iconClass = 'fa-bell text-warning';

    toast.innerHTML = `
        <i class="fa-solid ${iconClass}"></i>
        <div style="flex: 1; font-size: 0.88rem;">${message}</div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Mini Camera Widget Collapse/Expand Toggle
function toggleMiniCamera() {
    const widget = document.getElementById('miniCameraWidget');
    const icon = document.getElementById('miniCamToggleIcon');
    if (widget) {
        widget.classList.toggle('collapsed');
        if (icon) {
            icon.className = widget.classList.contains('collapsed') 
                ? 'fa-solid fa-chevron-down' 
                : 'fa-solid fa-chevron-up';
        }
    }
}

// Personnel View Switcher (Grid vs Table)
function setPersonnelView(mode) {
    const gridView = document.getElementById('personnelGridView');
    const tableView = document.getElementById('personnelTableView');
    const gridBtn = document.getElementById('viewGridBtn');
    const tableBtn = document.getElementById('viewTableBtn');

    if (!gridView || !tableView) return;

    if (mode === 'table') {
        gridView.style.display = 'none';
        tableView.style.display = 'block';
        if (gridBtn) gridBtn.classList.remove('active');
        if (tableBtn) tableBtn.classList.add('active');
        localStorage.setItem('personnel_view_pref', 'table');
    } else {
        gridView.style.display = 'grid';
        tableView.style.display = 'none';
        if (gridBtn) gridBtn.classList.add('active');
        if (tableBtn) tableBtn.classList.remove('active');
        localStorage.setItem('personnel_view_pref', 'grid');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('personnelGridView')) {
        const savedView = localStorage.getItem('personnel_view_pref') || 'grid';
        setPersonnelView(savedView);
    }
});
