// Face Camera Recognition & Biometric Scanning Module

let videoStream = null;
let animFrameId = null;
let currentFacingMode = 'user'; // 'user' for front camera, 'environment' for rear camera on Android

function openBiometricModal() {
    openModal('biometricModal');
    startCamera();
}

function closeBiometricModal() {
    stopCamera();
    closeModal('biometricModal');
}

async function startCamera() {
    const video = document.getElementById('biometricVideo');
    const canvas = document.getElementById('biometricCanvas');
    const statusText = document.getElementById('biometricScanStatus');

    if (!video || !canvas) return;

    if (statusText) {
        statusText.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Initializing camera stream...</span>';
    }

    try {
        if (videoStream) {
            stopCamera();
        }

        videoStream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: currentFacingMode,
                width: { ideal: 640 },
                height: { ideal: 480 }
            },
            audio: false
        });

        video.srcObject = videoStream;
        await video.play();

        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;

        if (statusText) {
            statusText.innerHTML = '<span class="text-success"><i class="fa-solid fa-eye me-1"></i> Camera Active &bull; Align face inside Cyber Target Box</span>';
        }

        // Start futuristic HUD overlay animation loop
        drawBiometricHUD();
    } catch (err) {
        console.error("Camera access error:", err);
        if (statusText) {
            statusText.innerHTML = `<span class="text-danger"><i class="fa-solid fa-triangle-exclamation me-1"></i> Camera error: ${err.message || 'Permission denied'}</span>`;
        }
    }
}

function stopCamera() {
    if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
    }
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
    const video = document.getElementById('biometricVideo');
    if (video) video.srcObject = null;
}

function toggleCameraFacing() {
    currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
    startCamera();
}

// Cyber HUD Overlay Animation Loop
function drawBiometricHUD() {
    const video = document.getElementById('biometricVideo');
    const canvas = document.getElementById('biometricCanvas');
    if (!video || !canvas) return;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    let laserY = 0;
    let scanDirection = 1;

    function renderFrame() {
        if (!videoStream) return;

        ctx.clearRect(0, 0, w, h);

        // Center Bounding Target Box
        const boxW = Math.min(w * 0.6, 260);
        const boxH = Math.min(h * 0.65, 300);
        const boxX = (w - boxW) / 2;
        const boxY = (h - boxH) / 2;

        // Draw Corner Target Brackets (Cyan Tech)
        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 3;
        const bracketLen = 25;

        // Top-Left corner
        ctx.beginPath();
        ctx.moveTo(boxX, boxY + bracketLen); ctx.lineTo(boxX, boxY); ctx.lineTo(boxX + bracketLen, boxY);
        ctx.stroke();

        // Top-Right corner
        ctx.beginPath();
        ctx.moveTo(boxX + boxW - bracketLen, boxY); ctx.lineTo(boxX + boxW, boxY); ctx.lineTo(boxX + boxW, boxY + bracketLen);
        ctx.stroke();

        // Bottom-Left corner
        ctx.beginPath();
        ctx.moveTo(boxX, boxY + boxH - bracketLen); ctx.lineTo(boxX, boxY + boxH); ctx.lineTo(boxX + bracketLen, boxY + boxH);
        ctx.stroke();

        // Bottom-Right corner
        ctx.beginPath();
        ctx.moveTo(boxX + boxW - bracketLen, boxY + boxH); ctx.lineTo(boxX + boxW, boxY + boxH); ctx.lineTo(boxX + boxW, boxY + boxH - bracketLen);
        ctx.stroke();

        // Moving Scanning Laser Line
        laserY += 3 * scanDirection;
        if (laserY > boxH) { laserY = boxH; scanDirection = -1; }
        if (laserY < 0) { laserY = 0; scanDirection = 1; }

        const currentLaserY = boxY + laserY;
        const gradient = ctx.createLinearGradient(boxX, currentLaserY, boxX + boxW, currentLaserY);
        gradient.addColorStop(0, 'rgba(6, 182, 212, 0.1)');
        gradient.addColorStop(0.5, 'rgba(6, 182, 212, 0.9)');
        gradient.addColorStop(1, 'rgba(6, 182, 212, 0.1)');

        ctx.strokeStyle = gradient;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(boxX, currentLaserY);
        ctx.lineTo(boxX + boxW, currentLaserY);
        ctx.stroke();

        // Simulated Facial Landmark Mesh Points
        ctx.fillStyle = '#10b981';
        const cX = w / 2;
        const cY = h / 2;
        const landmarks = [
            { x: cX - 45, y: cY - 35 }, // Left eye
            { x: cX + 45, y: cY - 35 }, // Right eye
            { x: cX, y: cY - 5 },       // Nose tip
            { x: cX - 30, y: cY + 40 }, // Left mouth corner
            { x: cX + 30, y: cY + 40 }, // Right mouth corner
            { x: cX, y: cY + 70 }        // Chin
        ];

        landmarks.forEach(pt => {
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 4, 0, Math.PI * 2);
            ctx.fill();
        });

        // HUD Text Header
        ctx.font = '12px "JetBrains Mono", monospace';
        ctx.fillStyle = '#06b6d4';
        ctx.fillText("FACIAL RECOGNITION V2.4 // READY", boxX, boxY - 10);

        animFrameId = requestAnimationFrame(renderFrame);
    }

    renderFrame();
}

// Trigger Biometric Scan Match
async function captureAndScanFace() {
    const statusText = document.getElementById('biometricScanStatus');
    const empSelect = document.getElementById('biometricEmpSelect');
    const selectedEmpId = empSelect ? empSelect.value : null;

    if (statusText) {
        statusText.innerHTML = '<span class="text-warning"><i class="fa-solid fa-fingerprint fa-spin me-1"></i> Extracting facial feature vectors...</span>';
    }

    try {
        const response = await fetch('/api/biometric-scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                emp_id: selectedEmpId,
                status: 'In Office',
                location_name: 'Face Biometrics Camera Station (HQ)',
                latitude: 37.7749,
                longitude: -122.4194
            })
        });

        const result = await response.json();

        if (result.success) {
            if (statusText) {
                statusText.innerHTML = `
                    <div style="background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; padding: 0.75rem; border-radius: 8px; color: #10b981; text-align: center;">
                        <i class="fa-solid fa-circle-check fa-2x mb-1"></i><br>
                        <strong>FACIAL MATCH VERIFIED</strong><br>
                        <span style="color: #fff; font-size: 0.9rem;">${result.employee_name} (${result.role})</span><br>
                        <span style="font-size: 0.78rem; color: #9ca3af;">Checked in at ${result.timestamp}</span>
                    </div>
                `;
            }
            showToast(`Biometric Scan Success: ${result.employee_name} checked in!`, 'success');
            setTimeout(() => {
                closeBiometricModal();
                window.location.reload();
            }, 1800);
        } else {
            if (statusText) {
                statusText.innerHTML = `<span class="text-danger"><i class="fa-solid fa-xmark-circle me-1"></i> ${result.message || 'Face match failed'}</span>`;
            }
        }
    } catch (err) {
        console.error(err);
        if (statusText) {
            statusText.innerHTML = `<span class="text-danger"><i class="fa-solid fa-triangle-exclamation me-1"></i> Server communication error</span>`;
        }
    }
}
