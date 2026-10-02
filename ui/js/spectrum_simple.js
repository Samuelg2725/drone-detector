// Simple spectrum viewer that definitely works
let spectrumCtx = null;
let spectrumRunning = true;

function initSimpleSpectrum() {
    const canvas = document.getElementById('fullSpectrumCanvas');
    if (!canvas) {
        console.log('Canvas not found, retrying...');
        setTimeout(initSimpleSpectrum, 500);
        return;
    }
    
    spectrumCtx = canvas.getContext('2d');
    canvas.width = canvas.clientWidth;
    canvas.height = canvas.clientHeight;
    
    console.log('Spectrum initialized!');
    drawSimpleSpectrum();
}

function drawSimpleSpectrum() {
    if (!spectrumCtx || !spectrumRunning) return;
    
    const canvas = document.getElementById('fullSpectrumCanvas');
    const width = canvas.width;
    const height = canvas.height;
    const ctx = spectrumCtx;
    
    // Generate data
    const numPoints = 350;
    const powers = [];
    
    for (let i = 0; i < numPoints; i++) {
        const freq = 2.4 + (i / numPoints) * 3.5; // 2.4 to 5.9 GHz
        
        let power = -95 + Math.random() * 15;
        
        // Drone signals
        if (Math.abs(freq - 2.45) < 0.03) power += 25;
        if (Math.abs(freq - 5.8) < 0.03) power += 25;
        if (Math.abs(freq - 5.81) < 0.02) power += 20;
        if (Math.abs(freq - 2.48) < 0.02) power += 30;
        
        powers.push(Math.min(-40, Math.max(-100, power)));
    }
    
    // Clear
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, width, height);
    
    // Draw grid
    ctx.strokeStyle = '#2a2a4e';
    ctx.lineWidth = 0.5;
    
    for (let i = 0; i <= 5; i++) {
        const y = height - (i * height / 5);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
        ctx.fillStyle = '#888';
        ctx.font = '10px monospace';
        ctx.fillText(`${-100 + i * 12} dBm`, 5, y - 3);
    }
    
    // Draw spectrum
    ctx.beginPath();
    ctx.strokeStyle = '#00ff88';
    ctx.lineWidth = 2;
    
    for (let i = 0; i < powers.length; i++) {
        const x = (i / powers.length) * width;
        const normalized = (powers[i] + 100) / 60;
        const y = height - Math.min(Math.max(normalized, 0), 1) * height;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();
    
    // Fill
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = 'rgba(0, 255, 136, 0.1)';
    ctx.fill();
    
    setTimeout(drawSimpleSpectrum, 500);
}

// Start when page loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSimpleSpectrum);
} else {
    initSimpleSpectrum();
}
