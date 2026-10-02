// Chart.js visualizations
let threatChart = null;
let trendChart = null;
let droneTypeChart = null;
let spectrumCtx = null;

function initCharts() {
    // Threat distribution chart
    const threatCtx = document.getElementById('threatChart')?.getContext('2d');
    if (threatCtx) {
        threatChart = new Chart(threatCtx, {
            type: 'doughnut',
            data: {
                labels: ['Low', 'Medium', 'High', 'Critical'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: ['#00ff88', '#ffaa00', '#ff6600', '#ff0000'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#e0e0e0' } }
                }
            }
        });
    }
    
    // Spectrum canvas
    spectrumCtx = document.getElementById('spectrumCanvas')?.getContext('2d');
    if (spectrumCtx) {
        drawSpectrum();
    }
    
    // Trend chart
    const trendCtx = document.getElementById('trendChart')?.getContext('2d');
    if (trendCtx) {
        trendChart = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Detections',
                    data: [],
                    borderColor: '#00ff88',
                    backgroundColor: 'rgba(0, 255, 136, 0.1)',
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: '#e0e0e0' } } },
                scales: { y: { grid: { color: '#2a2a4e' } }, x: { grid: { color: '#2a2a4e' } } }
            }
        });
    }
    
    // Drone type chart
    const typeCtx = document.getElementById('droneTypeChart')?.getContext('2d');
    if (typeCtx) {
        droneTypeChart = new Chart(typeCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Count',
                    data: [],
                    backgroundColor: '#00ff88',
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: '#e0e0e0' } } },
                scales: { y: { grid: { color: '#2a2a4e' } }, x: { grid: { color: '#2a2a4e' } } }
            }
        });
    }
}

function updateThreatChart(distribution) {
    if (threatChart && distribution) {
        threatChart.data.datasets[0].data = [
            distribution.low || 0,
            distribution.medium || 0,
            distribution.high || 0,
            distribution.critical || 0
        ];
        threatChart.update();
    }
}

async function updateTrends() {
    const period = document.getElementById('trendPeriod')?.value || 'day';
    try {
        const response = await fetch(`${apiBase}/api/v1/detections/stats`);
        const data = await response.json();
        if (data.status === 'success' && trendChart && droneTypeChart) {
            // Update drone type chart
            const droneTypes = data.data.drone_types || {};
            trendChart.data.labels = Object.keys(droneTypes);
            trendChart.data.datasets[0].data = Object.values(droneTypes);
            trendChart.update();
            
            // Update drone type chart
            droneTypeChart.data.labels = Object.keys(droneTypes);
            droneTypeChart.data.datasets[0].data = Object.values(droneTypes);
            droneTypeChart.update();
        }
    } catch (e) {
        console.error('Failed to update trends:', e);
    }
}

async function drawSpectrum() {
    if (!spectrumCtx) return;
    
    try {
        const response = await fetch(`${apiBase}/api/v1/spectrum/live`);
        const data = await response.json();
        if (data.status === 'success') {
            const spectrum = data.data.spectrum;
            const canvas = document.getElementById('spectrumCanvas');
            if (canvas) {
                const ctx = canvas.getContext('2d');
                const width = canvas.width;
                const height = canvas.height;
                
                ctx.clearRect(0, 0, width, height);
                
                // Draw grid
                ctx.strokeStyle = '#2a2a4e';
                ctx.lineWidth = 0.5;
                for (let i = 0; i <= 4; i++) {
                    const y = height - (i * height / 4);
                    ctx.beginPath();
                    ctx.moveTo(0, y);
                    ctx.lineTo(width, y);
                    ctx.stroke();
                }
                
                // Draw spectrum
                if (spectrum && spectrum.length) {
                    ctx.beginPath();
                    ctx.strokeStyle = '#00ff88';
                    ctx.lineWidth = 2;
                    
                    const step = width / spectrum.length;
                    for (let i = 0; i < spectrum.length; i++) {
                        const x = i * step;
                        const normalized = (spectrum[i] + 100) / 60;
                        const y = height - Math.min(Math.max(normalized, 0), 1) * height;
                        if (i === 0) ctx.moveTo(x, y);
                        else ctx.lineTo(x, y);
                    }
                    ctx.stroke();
                }
            }
        }
    } catch (e) {
        console.error('Failed to draw spectrum:', e);
    }
    
    requestAnimationFrame(drawSpectrum);
}

function startSpectrum() {
    drawSpectrum();
}
