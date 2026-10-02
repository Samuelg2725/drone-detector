// Map View Logic
let droneMap = null;
let droneMarkers = {};

function initMap() {
    if (droneMap) return;
    
    droneMap = L.map('droneMap').setView([37.7749, -122.4194], 13);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(droneMap);
    
    window.droneMap = droneMap;
}

function updateDroneMarker(detection) {
    if (!droneMap) initMap();
    
    const droneId = detection.drone_id;
    const pos = detection.position;
    const threatColor = getThreatColor(detection.threat_level);
    
    const popupContent = `
        <div style="min-width: 150px;">
            <strong>${detection.icon || '🚁'} ${detection.drone_type}</strong><br>
            <span style="color: ${threatColor}">Threat: ${detection.threat_level.toUpperCase()}</span><br>
            Confidence: ${(detection.confidence * 100).toFixed(0)}%<br>
            Freq: ${(detection.frequency / 1e9).toFixed(3)} GHz<br>
            Alt: ${pos.alt || 0}m<br>
            <small>${new Date(detection.timestamp).toLocaleTimeString()}</small>
        </div>
    `;
    
    if (droneMarkers[droneId]) {
        droneMarkers[droneId].setLatLng([pos.lat, pos.lon]);
        droneMarkers[droneId].setPopupContent(popupContent);
    } else {
        const marker = L.marker([pos.lat, pos.lon], {
            icon: L.divIcon({
                className: 'custom-div-icon',
                html: `<div style="background: ${threatColor}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px ${threatColor};"></div>`,
                iconSize: [16, 16],
                popupAnchor: [0, -8]
            })
        }).bindPopup(popupContent).addTo(droneMap);
        
        droneMarkers[droneId] = marker;
    }
}

function getThreatColor(threat) {
    const colors = {
        'low': '#00ff88',
        'medium': '#ffaa00',
        'high': '#ff6600',
        'critical': '#ff0000'
    };
    return colors[threat] || '#888888';
}

// Update all markers from detections array
function updateAllMarkers() {
    if (!detections) return;
    
    // Get latest detection per drone
    const latestDrone = {};
    detections.forEach(d => {
        if (!latestDrone[d.drone_id] || 
            new Date(d.timestamp) > new Date(latestDrone[d.drone_id].timestamp)) {
            latestDrone[d.drone_id] = d;
        }
    });
    
    Object.values(latestDrone).forEach(d => updateDroneMarker(d));
}
