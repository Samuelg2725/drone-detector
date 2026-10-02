// WebSocket Configuration
const WS_URL = 'ws://localhost:8082/';
let ws = null;
let detections = [];
let plotData = { event_numbers: [], confidences: [] };
let confidenceChart = null;

// Initialize WebSocket Connection
function initWebSocket() {
    ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
        console.log('WebSocket connected to', WS_URL);
        updateConnectionStatus(true);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
        setTimeout(initWebSocket, 3000); // Auto-reconnect
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        showAlert('WebSocket connection error', 'error');
    };
    
    ws.onmessage = handleWebSocketMessage;
}

// Handle incoming WebSocket messages
function handleWebSocketMessage(event) {
    try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
            case 'metrics':
                updateMetrics(data.data);
                break;
            case 'plot_data':
                updatePlotData(data.data);
                break;
            case 'detection':
                addDetection(data.data);
                break;
            case 'alert':
                showAlert(data.data.message, data.data.level || 'warning');
                break;
            case 'status':
                updateSystemStatus(data.data);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    } catch (error) {
        console.error('Error parsing WebSocket message:', error);
    }
}

// Update metrics display
function updateMetrics(metrics) {
    document.getElementById('totalDetections').textContent = metrics.total_detections || 0;
    document.getElementById('truePositives').textContent = metrics.true_positives || 0;
    document.getElementById('falsePositives').textContent = metrics.false_positives || 0;
    document.getElementById('avgProcessingTime').textContent = 
        (metrics.avg_processing_time || 0).toFixed(2) + ' ms';
    
    // Sensor uptime
    if (metrics.sensor_uptime && metrics.sensor_uptime.length >= 4) {
        document.getElementById('rfUptime').textContent = metrics.sensor_uptime[0].toFixed(2) + ' s';
        document.getElementById('lidarUptime').textContent = metrics.sensor_uptime[1].toFixed(2) + ' s';
        document.getElementById('cameraUptime').textContent = metrics.sensor_uptime[2].toFixed(2) + ' s';
        document.getElementById('radarUptime').textContent = metrics.sensor_uptime[3].toFixed(2) + ' s';
    }
    
    document.getElementById('systemUptime').textContent = 
        ((metrics.system_uptime || 0) / 60).toFixed(2);
}

// Update confidence graph
function updatePlotData(data) {
    if (data.event_numbers && data.event_numbers.length > 0) {
        plotData.event_numbers.push(data.event_numbers[0]);
        plotData.confidences.push(data.confidences[0]);
        
        // Keep last 700 points
        if (plotData.event_numbers.length > 700) {
            plotData.event_numbers.shift();
            plotData.confidences.shift();
        }
        
        updateConfidenceGraph();
    }
}

// Initialize or update confidence graph
function updateConfidenceGraph() {
    const ctx = document.getElementById('confidenceGraph').getContext('2d');
    
    if (!confidenceChart) {
        confidenceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: plotData.event_numbers,
                datasets: [
                    {
                        label: 'Detection Confidence',
                        data: plotData.confidences,
                        borderColor: '#2196F3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)',
                        fill: true,
                        pointRadius: 0,
                        borderWidth: 2
                    },
                    {
                        label: 'Alert Threshold (0.625)',
                        data: plotData.event_numbers.map(() => 0.625),
                        borderColor: '#f44336',
                        borderDash: [5, 5],
                        fill: false,
                        pointRadius: 0,
                        borderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        min: 0.25,
                        max: 0.75,
                        title: { display: true, text: 'Confidence Level', color: '#fff' },
                        grid: { color: 'rgba(255,255,255,0.1)' }
                    },
                    x: {
                        title: { display: true, text: 'Detection Event Number', color: '#fff' },
                        grid: { color: 'rgba(255,255,255,0.1)' }
                    }
                },
                plugins: {
                    legend: { position: 'top', labels: { color: '#fff' } },
                    tooltip: { mode: 'index', intersect: false }
                },
                animation: false
            }
        });
    } else {
        confidenceChart.data.labels = plotData.event_numbers;
        confidenceChart.data.datasets[0].data = plotData.confidences;
        confidenceChart.data.datasets[1].data = plotData.event_numbers.map(() => 0.625);
        confidenceChart.update();
    }
}

// Add detection to table
function addDetection(detection) {
    detections.unshift(detection);
    
    // Keep only last 50 detections
    if (detections.length > 50) {
        detections.pop();
    }
    
    updateDetectionsTable();
}

// Update detections table
function updateDetectionsTable() {
    const tbody = document.getElementById('detectionsTable');
    
    if (detections.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No detections yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = detections.map(d => `
        <tr class="threat-${(d.threat_level || 'low').toLowerCase()}">
            <td>${d.timestamp || new Date().toLocaleTimeString()}</td>
            <td>${d.drone_type || 'Unknown'}</td>
            <td class="confidence-${getConfidenceClass(d.confidence)}">
                ${((d.confidence || 0) * 100).toFixed(1)}%
            </td>
            <td><span class="threat-badge threat-${(d.threat_level || 'low').toLowerCase()}">
                ${(d.threat_level || 'LOW').toUpperCase()}
            </span></td>
            <td>(${formatPosition(d.position)})</td>
            <td>(${formatVelocity(d.velocity)})</td>
        </tr>
    `).join('');
}

// Helper functions
function getConfidenceClass(confidence) {
    if (confidence >= 0.7) return 'high';
    if (confidence >= 0.5) return 'medium';
    return 'low';
}

function formatPosition(pos) {
    if (!pos || !Array.isArray(pos)) return '0,0,0';
    return pos.map(v => v.toFixed(2)).join(',');
}

function formatVelocity(vel) {
    if (!vel || !Array.isArray(vel)) return '0,0,0';
    return vel.map(v => v.toFixed(2)).join(',');
}

// Show alert
function showAlert(message, level = 'warning') {
    const alertsDiv = document.getElementById('alerts');
    const noAlertsDiv = document.getElementById('noAlertsMsg');
    
    noAlertsDiv.style.display = 'none';
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${level}`;
    alertDiv.innerHTML = `
        <span class="alert-icon">${getAlertIcon(level)}</span>
        <span class="alert-message">${message}</span>
        <span class="alert-time">${new Date().toLocaleTimeString()}</span>
        <button class="alert-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    alertsDiv.insertBefore(alertDiv, alertsDiv.firstChild);
    
    // Auto-remove after 10 seconds
    setTimeout(() => {
        if (alertDiv.parentElement) alertDiv.remove();
        if (alertsDiv.children.length === 0) {
            noAlertsDiv.style.display = 'block';
        }
    }, 10000);
}

function getAlertIcon(level) {
    switch(level) {
        case 'high': return '🔴';
        case 'medium': return '🟡';
        case 'error': return '⚠️';
        default: return '🔵';
    }
}

// Send command via WebSocket
function sendCommand(command) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(command);
        console.log('Command sent:', command);
    } else {
        showAlert('WebSocket not connected', 'error');
    }
}

// Clear detections
function clearDetections() {
    if (confirm('Are you sure you want to clear all detections?')) {
        sendCommand('clear_detections');
        detections = [];
        updateDetectionsTable();
        showAlert('Detections cleared', 'info');
    }
}

// Export data
function exportData() {
    const data = {
        timestamp: new Date().toISOString(),
        detections: detections,
        metrics: {
            total_detections: document.getElementById('totalDetections').textContent,
            true_positives: document.getElementById('truePositives').textContent,
            false_positives: document.getElementById('falsePositives').textContent
        }
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `drone_detections_${new Date().toISOString()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    showAlert('Data exported successfully', 'info');
}

// Update connection status
function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('systemStatus');
    if (connected) {
        statusEl.innerHTML = '● Connected';
        statusEl.className = 'status-badge connected';
    } else {
        statusEl.innerHTML = '● Disconnected';
        statusEl.className = 'status-badge disconnected';
    }
}

function updateSystemStatus(status) {
    const statusEl = document.getElementById('systemStatus');
    statusEl.innerHTML = `● ${status.state || 'Unknown'}`;
    statusEl.className = `status-badge ${(status.state || '').toLowerCase()}`;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
});