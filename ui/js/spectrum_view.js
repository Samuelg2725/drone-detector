// Real-time Spectrum Analyzer for 2.4GHz - 5.8GHz
let spectrumCtx = null;
let spectrumAnimationId = null;
let spectrumLive = true;
let currentBand = 'full'; // full, 2.4, 5.8
let waterfallData = [];
let peakHoldData = null;
let smoothingLevel = 3;

// Frequency bands
const BANDS = {
    '2.4': { start: 2.4, end: 2.5, label: '2.4 GHz Band', color: '#ffaa00' },
    '5.8': { start: 5.725, end: 5.875, label: '5.8 GHz Band', color: '#ff6600' },
    'full': { start: 2.4, end: 5.9, label: 'Full Spectrum (2.4 - 5.8 GHz)', color: '#00ff88' }
};

function initSpectrum() {
    const canvas = document.getElementById('fullSpectrumCanvas');
    if (canvas) {
        spectrumCtx = canvas.getContext('2d');
        canvas.width = 900;
        canvas.height = 350;
    }
    
    // Setup refresh rate listener
    const refreshSlider = document.getElementById('spectrumRefreshRate');
    if (refreshSlider) {
        refreshSlider.addEventListener('input', (e) => {
            document.getElementById('refreshRateValue').innerText = e.target.value + 'ms';
            if (spectrumLive) {
                stopSpectrumLive();
                startSpectrumLive();
            }
        });
    }
    
    // Setup smoothing listener
    const smoothSlider = document.getElementById('smoothing');
    if (smoothSlider) {
        smoothSlider.addEventListener('input', (e) => {
            smoothingLevel = parseInt(e.target.value);
        });
    }
    
    startSpectrumLive();
}

function startSpectrumLive() {
    spectrumLive = true;
    drawSpectrumFull();
}

function stopSpectrumLive() {
    spectrumLive = false;
    if (spectrumAnimationId) {
        cancelAnimationFrame(spectrumAnimationId);
        spectrumAnimationId = null;
    }
}

function toggleSpectrumRange() {
    if (currentBand === 'full') currentBand = '2.4';
    else if (currentBand === '2.4') currentBand = '5.8';
    else currentBand = 'full';
    
    updateSpectrumBandLabel();
}

function updateSpectrumBandLabel() {
    const band = BANDS[currentBand];
    const header = document.querySelector('.spectrum-panel .panel-header h3');
    if (header) {
        header.innerHTML = `<i class="fas fa-waveform"></i> REAL-TIME SPECTRUM - ${band.label}`;
    }
}

function setSpectrumBand(band) {
    currentBand = band;
    updateSpectrumBandLabel();
    drawSpectrumFull();
}

function generateSpectrumData() {
    // Generate realistic spectrum data for 2.4GHz - 5.9GHz range
    const startFreq = BANDS[currentBand].start;
    const endFreq = BANDS[currentBand].end;
    const numPoints = currentBand === 'full' ? 350 : 200;
    
    const frequencies = [];
    const powers = [];
    
    for (let i = 0; i < numPoints; i++) {
        const freq = startFreq + (i / numPoints) * (endFreq - startFreq);
        frequencies.push(freq);
        
        // Base noise floor (-100 to -85 dBm)
        let power = -95 + Math.random() * 15;
        
        // Add peaks for drone signals at specific frequencies
        // DJI drones at 2.45 GHz
        if (Math.abs(freq - 2.45) < 0.03) {
            power += 25 + Math.random() * 10;
        }
        // DJI at 5.8 GHz
        if (Math.abs(freq - 5.8) < 0.03) {
            power += 25 + Math.random() * 10;
        }
        // FPV at 5.8 GHz
        if (Math.abs(freq - 5.81) < 0.02) {
            power += 20 + Math.random() * 8;
        }
        // Custom drone at 2.48 GHz
        if (Math.abs(freq - 2.48) < 0.02) {
            power += 30 + Math.random() * 5;
        }
        // Wi-Fi interference at 2.412, 2.437, 2.462
        if ([2.412, 2.437, 2.462].some(wf => Math.abs(freq - wf) < 0.01)) {
            power += 12 + Math.random() * 6;
        }
        
        // Apply smoothing
        if (i > 0 && smoothingLevel > 0) {
            const smoothFactor = smoothingLevel / 10;
            power = power * (1 - smoothFactor) + powers[i-1] * smoothFactor;
        }
        
        powers.push(Math.min(-40, Math.max(-100, power)));
    }
    
    return { frequencies, powers };
}

function drawSpectrumFull() {
    if (!spectrumLive) return;
    if (!spectrumCtx) {
        const canvas = document.getElementById('fullSpectrumCanvas');
        if (canvas) spectrumCtx = canvas.getContext('2d');
        else return;
    }
    
    const canvas = document.getElementById('fullSpectrumCanvas');
    const width = canvas.width;
    const height = canvas.height;
    const ctx = spectrumCtx;
    
    // Generate data
    const { frequencies, powers } = generateSpectrumData();
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Draw background grid
    ctx.strokeStyle = '#2a2a4e';
    ctx.lineWidth = 0.5;
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, width, height);
    
    // Horizontal grid lines (power levels)
    for (let i = 0; i <= 5; i++) {
        const y = height - (i * height / 5);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
        
        // Power labels
        ctx.fillStyle = '#888';
        ctx.font = '10px monospace';
        ctx.fillText(`${-100 + i * 12} dBm`, 5, y - 3);
    }
    
    // Vertical grid lines (frequency)
    const freqStart = BANDS[currentBand].start;
    const freqEnd = BANDS[currentBand].end;
    for (let freq = Math.ceil(freqStart * 10) / 10; freq <= freqEnd; freq += 0.1) {
        const x = ((freq - freqStart) / (freqEnd - freqStart)) * width;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
        
        // Frequency labels
        ctx.fillStyle = '#888';
        ctx.font = '10px monospace';
        ctx.fillText(`${freq.toFixed(1)} GHz`, x - 15, height - 5);
    }
    
    // Mark drone frequency bands
    const droneBands = [
        { freq: 2.45, label: 'DJI 2.4GHz', color: '#ffaa00' },
        { freq: 5.8, label: 'DJI/FPV 5.8GHz', color: '#ff6600' },
        { freq: 2.48, label: 'Custom Band', color: '#ff0000' }
    ];
    
    droneBands.forEach(band => {
        if (band.freq >= freqStart && band.freq <= freqEnd) {
            const x = ((band.freq - freqStart) / (freqEnd - freqStart)) * width;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.strokeStyle = band.color;
            ctx.lineWidth = 1;
            ctx.stroke();
            
            ctx.fillStyle = band.color;
            ctx.font = '8px monospace';
            ctx.fillText(band.label, x - 20, 15);
        }
    });
    
    // Draw the spectrum line
    ctx.beginPath();
    ctx.strokeStyle = BANDS[currentBand].color;
    ctx.lineWidth = 2;
    
    for (let i = 0; i < powers.length; i++) {
        const x = (i / powers.length) * width;
        // Map power (-100 to -40 dBm) to Y coordinate (height to 0)
        const normalizedPower = (powers[i] + 100) / 60;
        const y = height - Math.min(Math.max(normalizedPower, 0), 1) * height;
        
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();
    
    // Fill under the curve
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = `rgba(0, 255, 136, 0.1)`;
    ctx.fill();
    
    // Draw peaks if enabled
    const showPeaks = document.getElementById('showPeaks')?.checked;
    if (showPeaks) {
        ctx.fillStyle = '#ff0000';
        for (let i = 1; i < powers.length - 1; i++) {
            if (powers[i] > powers[i-1] && powers[i] > powers[i+1] && powers[i] > -70) {
                const x = (i / powers.length) * width;
                const y = height - ((powers[i] + 100) / 60) * height;
                ctx.beginPath();
                ctx.arc(x, y, 4, 0, 2 * Math.PI);
                ctx.fillStyle = '#ff0000';
                ctx.fill();
                ctx.fillStyle = '#fff';
                ctx.font = '10px monospace';
                ctx.fillText(`${Math.round(powers[i])}dBm`, x - 15, y - 5);
            }
        }
    }
    
    // Update spectrum stats
    const maxPower = Math.max(...powers);
    const minPower = Math.min(...powers);
    const avgPower = powers.reduce((a, b) => a + b, 0) / powers.length;
    
    const statsHtml = `
        <div class="spectrum-stats-grid">
            <div class="stat-item"><strong>Peak:</strong> ${Math.round(maxPower)} dBm</div>
            <div class="stat-item"><strong>Noise Floor:</strong> ${Math.round(minPower)} dBm</div>
            <div class="stat-item"><strong>Average:</strong> ${Math.round(avgPower)} dBm</div>
            <div class="stat-item"><strong>Dynamic Range:</strong> ${Math.round(maxPower - minPower)} dB</div>
            <div class="stat-item"><strong>Active Drones:</strong> ${detections ? detections.filter(d => {
                const freqGHz = d.frequency / 1e9;
                return freqGHz >= freqStart && freqGHz <= freqEnd;
            }).length : 0}</div>
            <div class="stat-item"><strong>Refresh:</strong> ${document.getElementById('spectrumRefreshRate')?.value || 500}ms</div>
        </div>
    `;
    
    const statsDiv = document.getElementById('spectrumStats');
    if (statsDiv) statsDiv.innerHTML = statsHtml;
    
    // Update waterfall
    updateWaterfall(powers);
    
    // Schedule next frame
    if (spectrumLive) {
        const refreshRate = parseInt(document.getElementById('spectrumRefreshRate')?.value || 500);
        spectrumAnimationId = setTimeout(() => {
            drawSpectrumFull();
        }, refreshRate);
    }
}

function updateWaterfall(powers) {
    // Add current spectrum to waterfall
    waterfallData.unshift(powers.slice());
    if (waterfallData.length > 100) waterfallData.pop();
    
    const canvas = document.getElementById('waterfallCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    ctx.clearRect(0, 0, width, height);
    
    // Draw waterfall
    const rowHeight = height / Math.min(waterfallData.length, 100);
    for (let row = 0; row < Math.min(waterfallData.length, 100); row++) {
        const data = waterfallData[row];
        if (!data) continue;
        
        for (let col = 0; col < data.length; col++) {
            const power = data[col];
            // Color based on power: green (-100) to red (-40)
            const intensity = Math.min(255, Math.max(0, Math.floor(((power + 100) / 60) * 255)));
            const color = `rgb(${intensity}, ${255 - intensity}, 0)`;
            
            ctx.fillStyle = color;
            ctx.fillRect(
                (col / data.length) * width,
                row * rowHeight,
                width / data.length,
                rowHeight
            );
        }
    }
    
    // Draw frequency labels
    ctx.fillStyle = '#fff';
    ctx.font = '10px monospace';
    ctx.fillText('2.4 GHz', 0, height - 5);
    ctx.fillText('5.8 GHz', width - 40, height - 5);
    ctx.fillStyle = '#888';
    ctx.fillText('← Past', 5, 15);
    ctx.fillText('Now →', width - 40, height - 10);
}

// Export for global access
window.startSpectrumLive = startSpectrumLive;
window.stopSpectrumLive = stopSpectrumLive;
window.toggleSpectrumRange = toggleSpectrumRange;
window.setSpectrumBand = setSpectrumBand;
window.drawSpectrumFull = drawSpectrumFull;
