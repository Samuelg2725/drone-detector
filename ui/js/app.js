// Main Application Logic
let apiBase = 'http://localhost:8888';
let wsConnection = null;
let detections = [];
let charts = {};
let map = null;
let markers = {};
let refreshInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initApp();
    setupEventListeners();
    connectWebSocket();
    startAutoRefresh();
});

function initApp() {
    console.log('Drone Detector Dashboard Initialized');
    loadSystemInfo();
    loadDetections();
    loadStats();
    initCharts();
    
    // Load saved settings
    document.getElementById('alertsEnabled').checked = localStorage.getItem('alertsEnabled') === 'true';
    document.getElementById('soundEnabled').checked = localStorage.getItem('soundEnabled') === 'true';
    document.getElementById('refreshInterval').value = localStorage.getItem('refreshInterval') || 2000;
}

function setupEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            switchPage(page);
        });
    });
    
    // Settings
    document.getElementById('alertsEnabled').addEventListener('change', (e) => {
        localStorage.setItem('alertsEnabled', e.target.checked);
    });
    document.getElementById('soundEnabled').addEventListener('change', (e) => {
        localStorage.setItem('soundEnabled', e.target.checked);
    });
    document.getElementById('refreshInterval').addEventListener('change', (e) => {
        localStorage.setItem('refreshInterval', e.target.value);
        startAutoRefresh();
    });
}

function switchPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`${page}Page`).classList.add('active');
    
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === page) {
            item.classList.add('active');
        }
    });
    
    document.getElementById('pageTitle').innerText = page.charAt(0).toUpperCase() + page.slice(1);
    
    if (page === 'map' && map) {
        setTimeout(() => map.invalidateSize(), 100);
    } else if (page === 'detections') {
        loadDetections();
    }
}

function startAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    const interval = parseInt(document.getElementById('refreshInterval').value);
    refreshInterval = setInterval(() => {
        loadStats();
        if (document.getElementById('detectionsPage').classList.contains('active')) {
            loadDetections();
        }
    }, interval);
}

async function loadSystemInfo() {
    try {
        const response = await fetch(`${apiBase}/health`);
        const data = await response.json();
        document.getElementById('systemInfo').innerHTML = `
            <div class="info-row"><strong>Status:</strong> ${data.status}</div>
            <div class="info-row"><strong>Service:</strong> ${data.service}</div>
            <div class="info-row"><strong>Mock Mode:</strong> ${data.mock_mode ? 'Enabled' : 'Disabled'}</div>
            <div class="info-row"><strong>Active Drones:</strong> ${data.active_drones || 0}</div>
            <div class="info-row"><strong>Uptime:</strong> ${new Date(data.timestamp).toLocaleString()}</div>
        `;
    } catch (e) {
        console.error('Failed to load system info:', e);
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${apiBase}/api/v1/detections/stats`);
        const data = await response.json();
        if (data.status === 'success') {
            const stats = data.data;
            document.getElementById('statDroneTypes').innerText = stats.unique_drones || 0;
            document.getElementById('statHighThreat').innerText = stats.threat_distribution?.high || 0;
            document.getElementById('totalDetections').innerText = stats.total_detections || 0;
            
            // Calculate avg confidence
            let totalConf = 0;
            if (stats.drone_types) {
                const types = Object.values(stats.drone_types);
                document.getElementById('statDroneTypes').innerText = types.length;
            }
            
            updateThreatChart(stats.threat_distribution);
        }
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

async function loadDetections() {
    try {
        const response = await fetch(`${apiBase}/api/v1/detections?limit=50`);
        const data = await response.json();
        if (data.status === 'success') {
            detections = data.data;
            updateDetectionsTable();
            updateRecentTable();
            document.getElementById('totalDetections').innerText = data.total || detections.length;
            document.getElementById('activeDrones').innerText = data.active_drones || detections.length;
        }
    } catch (e) {
        console.error('Failed to load detections:', e);
    }
}

function updateDetectionsTable() {
    const tbody = document.getElementById('detectionsTableBody');
    const search = document.getElementById('searchInput')?.value.toLowerCase() || '';
    const threatFilter = document.getElementById('threatFilter')?.value || '';
    
    let filtered = detections;
    if (search) {
        filtered = filtered.filter(d => d.drone_type.toLowerCase().includes(search));
    }
    if (threatFilter) {
        filtered = filtered.filter(d => d.threat_level === threatFilter);
    }
    
    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">No detections found</td></tr>';
        return;
    }
    
    tbody.innerHTML = filtered.map(d => `
        <tr class="threat-${d.threat_level}">
            <td>${new Date(d.timestamp).toLocaleTimeString()}</td>
            <td><span class="drone-icon">${d.icon || '🚁'}</span> ${d.drone_type}</td>
            <td><span class="threat-badge threat-${d.threat_level}">${d.threat_level.toUpperCase()}</span></td>
            <td>${(d.confidence * 100).toFixed(0)}%</td>
            <td>${(d.frequency / 1e9).toFixed(3)} GHz</td>
            <td>${d.signal_power} dBm</td>
            <td>${d.position ? `${d.position.lat.toFixed(4)}, ${d.position.lon.toFixed(4)}` : 'N/A'}</td>
        </tr>
    `).join('');
}

function updateRecentTable() {
    const tbody = document.getElementById('recentTableBody');
    const recent = detections.slice(0, 10);
    
    if (recent.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading">No detections yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = recent.map(d => `
        <tr class="threat-${d.threat_level}">
            <td>${new Date(d.timestamp).toLocaleTimeString()}</td>
            <td><span class="drone-icon">${d.icon || '🚁'}</span> ${d.drone_type}</td>
            <td><span class="threat-badge threat-${d.threat_level}">${d.threat_level.toUpperCase()}</span></td>
            <td>${(d.confidence * 100).toFixed(0)}%</td>
            <td>${(d.frequency / 1e9).toFixed(3)} GHz</td>
            <td><button class="btn-icon" onclick="showOnMap('${d.drone_id}')"><i class="fas fa-map-marker-alt"></i></button></td>
        </tr>
    `).join('');
}

function showOnMap(droneId) {
    switchPage('map');
    const drone = detections.find(d => d.drone_id === droneId);
    if (drone && map && drone.position) {
        map.flyTo([drone.position.lat, drone.position.lon], 16);
    }
}

function refreshDetections() {
    loadDetections();
}

function injectRandomDrone() {
    const types = ["DJI Mavic 3", "DJI Mini", "FPV Analog", "FPV Digital", "Custom Build"];
    const randomType = types[Math.floor(Math.random() * types.length)];
    fetch(`${apiBase}/api/v1/mock/inject?drone_type=${randomType}`, {method: 'POST'})
        .then(() => {
            loadDetections();
            loadStats();
        })
        .catch(e => console.error('Failed to inject drone:', e));
}

// Global functions for HTML buttons
window.refreshDetections = refreshDetections;
window.injectRandomDrone = injectRandomDrone;
window.showOnMap = showOnMap;
