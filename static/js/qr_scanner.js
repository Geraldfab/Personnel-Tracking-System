// Background Continuous Touchless QR Scanner Module

let bgQrScanner = null;
let lastScannedPayload = null;
let lastScannedTime = 0;
const SCAN_COOLDOWN_MS = 10000; // 10-second cooldown per QR payload to prevent multi-scanning

document.addEventListener('DOMContentLoaded', () => {
    // Automatically start background camera scanner when website is active
    initBackgroundQrScanner();
});

function initBackgroundQrScanner() {
    let container = document.getElementById('backgroundQrReader');
    if (!container) {
        container = document.createElement('div');
        container.id = 'backgroundQrReader';
        container.className = 'mini-cam-viewport';
        document.body.appendChild(container);
    }

    try {
        bgQrScanner = new Html5Qrcode("backgroundQrReader");

        const config = {
            fps: 10,
            qrbox: { width: 120, height: 120 },
            aspectRatio: 1.33
        };

        // Prefer rear camera on mobile/Android, fallback to front/webcam
        bgQrScanner.start(
            { facingMode: "environment" },
            config,
            onBackgroundQrCodeSuccess,
            onBackgroundQrCodeError
        ).catch(err => {
            console.warn("Camera fallback to user/front:", err);
            bgQrScanner.start(
                { facingMode: "user" },
                config,
                onBackgroundQrCodeSuccess,
                onBackgroundQrCodeError
            ).catch(err2 => {
                console.warn("Background QR Scanner camera access unavailable:", err2);
            });
        });
    } catch (e) {
        console.error("Failed to initialize QR Scanner:", e);
    }
}

async function onBackgroundQrCodeSuccess(decodedText, decodedResult) {
    const now = Date.now();
    
    // Cooldown check: ignore duplicate pings within SCAN_COOLDOWN_MS
    if (decodedText === lastScannedPayload && (now - lastScannedTime) < SCAN_COOLDOWN_MS) {
        return;
    }

    lastScannedPayload = decodedText;
    lastScannedTime = now;

    console.log("Background QR Scan Detected:", decodedText);

    try {
        const response = await fetch('/api/qr-scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                qr_data: decodedText,
                status: 'In Office',
                location_name: 'Background Touchless QR Kiosk',
                latitude: 37.7749,
                longitude: -122.4194
            })
        });

        const result = await response.json();

        if (result.success) {
            playScanBeep();
            showToast(`⚡ Auto Check-In Saved! ${result.employee_name} (${result.emp_code})`, 'success');
            
            // If viewing dashboard or attendance table, reload after short delay to show update
            if (window.location.pathname === '/' || window.location.pathname === '/attendance') {
                setTimeout(() => window.location.reload(), 1500);
            }
        } else {
            console.warn("Background QR check-in failure:", result.message);
        }
    } catch (err) {
        console.error("Background QR scan network error:", err);
    }
}

function onBackgroundQrCodeError(errorMessage) {
    // Ignore routine frame parsing pings
}

// Audio beep for instant scan feedback
function playScanBeep() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // High pitch A5 tone
        gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.12);
    } catch (e) {
        // AudioContext not allowed without user interaction
    }
}
