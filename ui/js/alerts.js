/**
 * Drone Detection System - Alert Handling
 * Version: 2.0.0
 * 
 * This module provides comprehensive alert management capabilities,
 * including real-time alert display, notification handling,
 * alert acknowledgment, escalation tracking, and audio/visual alerts.
 */

// ============================================================================
// Alert Manager Class
// ============================================================================

class AlertManager {
    /**
     * Create a new alert manager
     * @param {Object} options - Configuration options
     */
    constructor(options = {}) {
        this.container = options.container || document.getElementById('alertsContainer');
        this.maxAlerts = options.maxAlerts || 50;
        this.soundEnabled = options.soundEnabled !== false;
        this.notificationsEnabled = options.notificationsEnabled !== false;
        this.autoAcknowledge = options.autoAcknowledge || false;
        this.autoAcknowledgeDelay = options.autoAcknowledgeDelay || 30000;
        
        // Alert storage
        this.alerts = [];
        this.activeAlerts = [];
        this.acknowledgedAlerts = new Set();
        this.resolvedAlerts = new Set();
        
        // Callbacks
        this.callbacks = {
            onNewAlert: options.onNewAlert || null,
            onAlertAcknowledged: options.onAlertAcknowledged || null,
            onAlertResolved: options.onAlertResolved || null,
            onAlertEscalated: options.onAlertEscalated || null
        };
        
        // Audio elements
        this.sounds = {
            critical: null,
            high: null,
            medium: null,
            low: null
        };
        
        // DOM elements
        this.alertsList = null;
        this.alertBadge = null;
        this.alertSoundToggle = null;
        
        // Auto-refresh timer
        this.refreshTimer = null;
        
        this.init();
    }
    
    /**
     * Initialize alert manager
     */
    init() {
        this.createAlertUI();
        this.loadSounds();
        this.loadInitialAlerts();
        this.setupWebSocket();
        this.setupEventListeners();
        this.requestNotificationPermission();
        this.startAutoRefresh();
    }
    
    /**
     * Create alert UI
     */
    createAlertUI() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="alert-header">
                <h3><i class="fas fa-bell"></i> Alerts</h3>
                <div class="alert-header-actions">
                    <button class="btn-icon" id="clearAllAlerts" title="Clear all alerts">
                        <i class="fas fa-trash"></i>
                    </button>
                    <button class="btn-icon" id="acknowledgeAllAlerts" title="Acknowledge all">
                        <i class="fas fa-check-double"></i>
                    </button>
                    <button class="btn-icon" id="toggleAlertSound" title="Toggle sound">
                        <i class="fas fa-volume-up"></i>
                    </button>
                    <button class="btn-icon" id="refreshAlerts" title="Refresh">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                </div>
            </div>
            <div class="alert-stats">
                <div class="alert-stat critical">
                    <span class="stat-label">Critical</span>
                    <span class="stat-count" id="criticalCount">0</span>
                </div>
                <div class="alert-stat high">
                    <span class="stat-label">High</span>
                    <span class="stat-count" id="highCount">0</span>
                </div>
                <div class="alert-stat medium">
                    <span class="stat-label">Medium</span>
                    <span class="stat-count" id="mediumCount">0</span>
                </div>
                <div class="alert-stat low">
                    <span class="stat-label">Low</span>
                    <span class="stat-count" id="lowCount">0</span>
                </div>
            </div>
            <div class="alerts-list" id="alertsList">
                <div class="no-alerts">No active alerts</div>
            </div>
            <div class="alert-footer">
                <span class="alert-total" id="alertTotal">0 total alerts</span>
                <button class="btn-link" id="viewAlertHistory">View History</button>
            </div>
        `;
        
        // Cache elements
        this.alertsList = this.container.querySelector('#alertsList');
        this.alertBadge = document.querySelector('.alert-badge');
        
        // Stat elements
        this.statElements = {
            critical: this.container.querySelector('#criticalCount'),
            high: this.container.querySelector('#highCount'),
            medium: this.container.querySelector('#mediumCount'),
            low: this.container.querySelector('#lowCount')
        };
        
        // Button handlers
        const clearBtn = this.container.querySelector('#clearAllAlerts');
        const acknowledgeBtn = this.container.querySelector('#acknowledgeAllAlerts');
        const soundToggle = this.container.querySelector('#toggleAlertSound');
        const refreshBtn = this.container.querySelector('#refreshAlerts');
        const historyBtn = this.container.querySelector('#viewAlertHistory');
        
        if (clearBtn) clearBtn.addEventListener('click', () => this.clearAllAlerts());
        if (acknowledgeBtn) acknowledgeBtn.addEventListener('click', () => this.acknowledgeAll());
        if (soundToggle) soundToggle.addEventListener('click', () => this.toggleSound());
        if (refreshBtn) refreshBtn.addEventListener('click', () => this.refreshAlerts());
        if (historyBtn) historyBtn.addEventListener('click', () => this.showAlertHistory());
        
        this.alertSoundToggle = soundToggle;
    }
    
    /**
     * Load alert sounds
     */
    loadSounds() {
        // Create audio elements
        this.sounds.critical = new Audio('/assets/sounds/alert_critical.mp3');
        this.sounds.high = new Audio('/assets/sounds/alert_high.mp3');
        this.sounds.medium = new Audio('/assets/sounds/alert_medium.mp3');
        this.sounds.low = new Audio('/assets/sounds/alert_low.mp3');
        
        // Set volumes
        this.sounds.critical.volume = 0.8;
        this.sounds.high.volume = 0.6;
        this.sounds.medium.volume = 0.4;
        this.sounds.low.volume = 0.2;
    }
    
    /**
     * Load initial alerts from API
     */
    async loadInitialAlerts() {
        try {
            const response = await fetch('/api/alerts?active=true&limit=100');
            const data = await response.json();
            if (data.success && data.data) {
                this.alerts = data.data.items || [];
                this.activeAlerts = this.alerts.filter(a => !a.resolved);
                this.updateAlertDisplay();
                this.updateAlertBadge();
            }
        } catch (error) {
            console.error('Failed to load alerts:', error);
        }
    }
    
    /**
     * Setup WebSocket for real-time alerts
     */
    setupWebSocket() {
        if (typeof getWebSocketManager !== 'undefined') {
            const ws = getWebSocketManager();
            ws.subscribe('alert', (data) => {
                this.addAlert(data);
            });
            ws.subscribe('alert_update', (data) => {
                this.updateAlert(data);
            });
        }
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Listen for page visibility to manage sound
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.muteSounds();
            }
        });
    }
    
    /**
     * Request notification permission
     */
    requestNotificationPermission() {
        if ('Notification' in window && this.notificationsEnabled) {
            Notification.requestPermission();
        }
    }
    
    /**
     * Start auto-refresh timer
     */
    startAutoRefresh() {
        this.refreshTimer = setInterval(() => {
            this.refreshAlerts();
        }, 30000);
    }
    
    // ========================================================================
    // Alert Management Methods
    // ========================================================================
    
    /**
     * Add a new alert
     * @param {Object} alert - Alert data
     */
    addAlert(alert) {
        // Check for duplicate
        if (this.alerts.some(a => a.id === alert.id)) return;
        
        // Add to collections
        this.alerts.unshift(alert);
        if (!alert.resolved) {
            this.activeAlerts.unshift(alert);
        }
        
        // Limit size
        if (this.alerts.length > this.maxAlerts * 2) {
            this.alerts = this.alerts.slice(0, this.maxAlerts * 2);
        }
        if (this.activeAlerts.length > this.maxAlerts) {
            this.activeAlerts = this.activeAlerts.slice(0, this.maxAlerts);
        }
        
        // Update UI
        this.updateAlertDisplay();
        this.updateAlertBadge();
        this.updateStatistics();
        
        // Play sound
        this.playAlertSound(alert.severity);
        
        // Show notification
        this.showNotification(alert);
        
        // Auto-acknowledge if configured
        if (this.autoAcknowledge && alert.severity !== 'CRITICAL') {
            setTimeout(() => {
                this.acknowledgeAlert(alert.id);
            }, this.autoAcknowledgeDelay);
        }
        
        // Trigger callback
        if (this.callbacks.onNewAlert) {
            this.callbacks.onNewAlert(alert);
        }
    }
    
    /**
     * Update an existing alert
     * @param {Object} alert - Updated alert data
     */
    updateAlert(alert) {
        const index = this.alerts.findIndex(a => a.id === alert.id);
        if (index !== -1) {
            this.alerts[index] = { ...this.alerts[index], ...alert };
            
            // Update active alerts
            if (alert.resolved) {
                this.activeAlerts = this.activeAlerts.filter(a => a.id !== alert.id);
                if (this.callbacks.onAlertResolved) {
                    this.callbacks.onAlertResolved(alert);
                }
            } else if (!this.activeAlerts.some(a => a.id === alert.id)) {
                this.activeAlerts.unshift(alert);
            }
            
            this.updateAlertDisplay();
            this.updateAlertBadge();
            this.updateStatistics();
        }
    }
    
    /**
     * Acknowledge an alert
     * @param {string} alertId - Alert ID
     * @param {string} user - User who acknowledged
     */
    async acknowledgeAlert(alertId, user = 'system') {
        try {
            const response = await fetch(`/api/alerts/${alertId}/acknowledge`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user })
            });
            
            const data = await response.json();
            if (data.success) {
                this.acknowledgedAlerts.add(alertId);
                this.updateAlertDisplay();
                
                if (this.callbacks.onAlertAcknowledged) {
                    this.callbacks.onAlertAcknowledged(alertId);
                }
            }
        } catch (error) {
            console.error('Failed to acknowledge alert:', error);
        }
    }
    
    /**
     * Resolve an alert
     * @param {string} alertId - Alert ID
     */
    async resolveAlert(alertId) {
        try {
            const response = await fetch(`/api/alerts/${alertId}/resolve`, {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.success) {
                this.resolvedAlerts.add(alertId);
                this.activeAlerts = this.activeAlerts.filter(a => a.id !== alertId);
                this.updateAlertDisplay();
                this.updateAlertBadge();
                this.updateStatistics();
                
                if (this.callbacks.onAlertResolved) {
                    const alert = this.alerts.find(a => a.id === alertId);
                    this.callbacks.onAlertResolved(alert);
                }
            }
        } catch (error) {
            console.error('Failed to resolve alert:', error);
        }
    }
    
    /**
     * Escalate an alert
     * @param {string} alertId - Alert ID
     */
    async escalateAlert(alertId) {
        try {
            const response = await fetch(`/api/alerts/${alertId}/escalate`, {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.success) {
                const alert = this.alerts.find(a => a.id === alertId);
                if (alert) {
                    alert.escalation_level = (alert.escalation_level || 0) + 1;
                    this.updateAlertDisplay();
                    
                    if (this.callbacks.onAlertEscalated) {
                        this.callbacks.onAlertEscalated(alert);
                    }
                }
            }
        } catch (error) {
            console.error('Failed to escalate alert:', error);
        }
    }
    
    /**
     * Acknowledge all active alerts
     */
    acknowledgeAll() {
        this.activeAlerts.forEach(alert => {
            if (!this.acknowledgedAlerts.has(alert.id)) {
                this.acknowledgeAlert(alert.id, 'user');
            }
        });
    }
    
    /**
     * Clear all alerts
     */
    clearAllAlerts() {
        if (confirm('Are you sure you want to clear all alerts?')) {
            this.alerts = [];
            this.activeAlerts = [];
            this.acknowledgedAlerts.clear();
            this.resolvedAlerts.clear();
            this.updateAlertDisplay();
            this.updateAlertBadge();
            this.updateStatistics();
        }
    }
    
    /**
     * Refresh alerts from server
     */
    async refreshAlerts() {
        try {
            const response = await fetch('/api/alerts?active=true&limit=100');
            const data = await response.json();
            if (data.success && data.data) {
                this.alerts = data.data.items || [];
                this.activeAlerts = this.alerts.filter(a => !a.resolved);
                this.updateAlertDisplay();
                this.updateAlertBadge();
                this.updateStatistics();
            }
        } catch (error) {
            console.error('Failed to refresh alerts:', error);
        }
    }
    
    // ========================================================================
    // UI Update Methods
    // ========================================================================
    
    /**
     * Update alert display
     */
    updateAlertDisplay() {
        if (!this.alertsList) return;
        
        if (this.activeAlerts.length === 0) {
            this.alertsList.innerHTML = '<div class="no-alerts"><i class="fas fa-check-circle"></i> No active alerts</div>';
            return;
        }
        
        this.alertsList.innerHTML = this.activeAlerts.map(alert => this.renderAlertItem(alert)).join('');
        
        // Attach event listeners to new elements
        this.attachAlertEventListeners();
    }
    
    /**
     * Render a single alert item
     * @param {Object} alert - Alert data
     * @returns {string} HTML string
     */
    renderAlertItem(alert) {
        const severityClass = alert.severity?.toLowerCase() || 'info';
        const isAcknowledged = this.acknowledgedAlerts.has(alert.id);
        const escalationLevel = alert.escalation_level || 0;
        
        return `
            <div class="alert-item alert-${severityClass} ${isAcknowledged ? 'acknowledged' : ''}" 
                 data-id="${alert.id}" data-severity="${severityClass}">
                <div class="alert-icon">
                    <i class="fas ${this.getAlertIcon(alert.severity)}"></i>
                </div>
                <div class="alert-content">
                    <div class="alert-header">
                        <span class="alert-title">${this.escapeHtml(alert.title || 'Alert')}</span>
                        <span class="alert-time">${this.formatRelativeTime(alert.timestamp)}</span>
                    </div>
                    <div class="alert-message">${this.escapeHtml(alert.message || 'No message')}</div>
                    ${escalationLevel > 0 ? `<div class="alert-escalation">Escalation Level: ${escalationLevel}</div>` : ''}
                    <div class="alert-actions">
                        ${!isAcknowledged ? `<button class="alert-acknowledge" data-id="${alert.id}">Acknowledge</button>` : ''}
                        <button class="alert-resolve" data-id="${alert.id}">Resolve</button>
                        ${escalationLevel < 3 ? `<button class="alert-escalate" data-id="${alert.id}">Escalate</button>` : ''}
                        <button class="alert-view" data-id="${alert.id}">View Details</button>
                    </div>
                </div>
                <div class="alert-severity-badge">
                    <span class="severity-badge severity-${severityClass}">${alert.severity || 'INFO'}</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Attach event listeners to alert items
     */
    attachAlertEventListeners() {
        // Acknowledge buttons
        document.querySelectorAll('.alert-acknowledge').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                this.acknowledgeAlert(id, 'user');
            });
        });
        
        // Resolve buttons
        document.querySelectorAll('.alert-resolve').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                this.resolveAlert(id);
            });
        });
        
        // Escalate buttons
        document.querySelectorAll('.alert-escalate').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                this.escalateAlert(id);
            });
        });
        
        // View details buttons
        document.querySelectorAll('.alert-view').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                this.showAlertDetails(id);
            });
        });
        
        // Alert item click
        document.querySelectorAll('.alert-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = item.dataset.id;
                this.showAlertDetails(id);
            });
        });
    }
    
    /**
     * Update alert badge in navigation
     */
    updateAlertBadge() {
        const totalActive = this.activeAlerts.length;
        const badge = document.querySelector('.alert-badge, .nav-item[data-page="alerts"] .badge');
        
        if (badge) {
            if (totalActive > 0) {
                badge.textContent = totalActive > 99 ? '99+' : totalActive;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
        
        // Update page title with alert count
        if (totalActive > 0) {
            document.title = `(${totalActive}) Drone Detection System`;
        } else {
            document.title = 'Drone Detection System';
        }
    }
    
    /**
     * Update alert statistics
     */
    updateStatistics() {
        const counts = {
            critical: this.activeAlerts.filter(a => a.severity === 'CRITICAL').length,
            high: this.activeAlerts.filter(a => a.severity === 'HIGH').length,
            medium: this.activeAlerts.filter(a => a.severity === 'MEDIUM').length,
            low: this.activeAlerts.filter(a => a.severity === 'LOW').length
        };
        
        if (this.statElements.critical) this.statElements.critical.textContent = counts.critical;
        if (this.statElements.high) this.statElements.high.textContent = counts.high;
        if (this.statElements.medium) this.statElements.medium.textContent = counts.medium;
        if (this.statElements.low) this.statElements.low.textContent = counts.low;
        
        const totalElement = this.container?.querySelector('#alertTotal');
        if (totalElement) {
            totalElement.textContent = `${this.activeAlerts.length} active alerts`;
        }
    }
    
    // ========================================================================
    // Audio/Visual Alerts
    // ========================================================================
    
    /**
     * Play alert sound based on severity
     * @param {string} severity - Alert severity
     */
    playAlertSound(severity) {
        if (!this.soundEnabled) return;
        
        const sound = this.sounds[severity?.toLowerCase()];
        if (sound) {
            // Stop and rewind
            sound.pause();
            sound.currentTime = 0;
            sound.play().catch(e => console.log('Audio play failed:', e));
        }
    }
    
    /**
     * Mute all sounds
     */
    muteSounds() {
        Object.values(this.sounds).forEach(sound => {
            if (sound) sound.volume = 0;
        });
    }
    
    /**
     * Unmute sounds
     */
    unmuteSounds() {
        this.sounds.critical.volume = 0.8;
        this.sounds.high.volume = 0.6;
        this.sounds.medium.volume = 0.4;
        this.sounds.low.volume = 0.2;
    }
    
    /**
     * Toggle sound on/off
     */
    toggleSound() {
        this.soundEnabled = !this.soundEnabled;
        if (this.alertSoundToggle) {
            const icon = this.alertSoundToggle.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-volume-up');
                icon.classList.toggle('fa-volume-mute');
            }
        }
        
        if (!this.soundEnabled) {
            this.muteSounds();
        } else {
            this.unmuteSounds();
        }
        
        localStorage.setItem('alertSoundEnabled', this.soundEnabled);
    }
    
    /**
     * Show browser notification
     * @param {Object} alert - Alert data
     */
    showNotification(alert) {
        if (!this.notificationsEnabled) return;
        
        if ('Notification' in window && Notification.permission === 'granted') {
            const notification = new Notification(`[${alert.severity}] ${alert.title}`, {
                body: alert.message,
                icon: '/assets/icons/alert.png',
                tag: alert.id,
                requireInteraction: alert.severity === 'CRITICAL'
            });
            
            notification.onclick = () => {
                window.focus();
                this.showAlertDetails(alert.id);
                notification.close();
            };
            
            // Auto-close after 10 seconds
            setTimeout(() => notification.close(), 10000);
        }
    }
    
    // ========================================================================
    // Detail Views
    // ========================================================================
    
    /**
     * Show alert details modal
     * @param {string} alertId - Alert ID
     */
    showAlertDetails(alertId) {
        const alert = this.alerts.find(a => a.id === alertId);
        if (!alert) return;
        
        const modal = this.createDetailModal(alert);
        document.body.appendChild(modal);
        modal.classList.add('active');
        
        // Close button
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => modal.remove());
        }
        
        // Action buttons
        const acknowledgeBtn = modal.querySelector('#modalAcknowledge');
        const resolveBtn = modal.querySelector('#modalResolve');
        const escalateBtn = modal.querySelector('#modalEscalate');
        
        if (acknowledgeBtn) {
            acknowledgeBtn.addEventListener('click', () => {
                this.acknowledgeAlert(alert.id, 'user');
                modal.remove();
            });
        }
        
        if (resolveBtn) {
            resolveBtn.addEventListener('click', () => {
                this.resolveAlert(alert.id);
                modal.remove();
            });
        }
        
        if (escalateBtn) {
            escalateBtn.addEventListener('click', () => {
                this.escalateAlert(alert.id);
                modal.remove();
            });
        }
    }
    
    /**
     * Create detail modal
     * @param {Object} alert - Alert data
     * @returns {HTMLElement} Modal element
     */
    createDetailModal(alert) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Alert Details</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="alert-detail-header">
                        <span class="severity-badge severity-${alert.severity?.toLowerCase()}">${alert.severity || 'INFO'}</span>
                        <span class="alert-time">${new Date(alert.timestamp).toLocaleString()}</span>
                    </div>
                    <h4>${this.escapeHtml(alert.title || 'Alert')}</h4>
                    <p>${this.escapeHtml(alert.message || 'No message')}</p>
                    
                    <div class="alert-detail-section">
                        <h5>Details</h5>
                        <table class="detail-table">
                            <tr><td>ID:</td><td>${alert.id}</td></tr>
                            <tr><td>Source:</td><td>${alert.source || 'System'}</td></tr>
                            <tr><td>Category:</td><td>${alert.category || 'General'}</td></tr>
                            <tr><td>Escalation Level:</td><td>${alert.escalation_level || 0}</td></tr>
                            ${alert.drone_id ? `<tr><td>Drone ID:</td><td>${alert.drone_id}</td></tr>` : ''}
                            ${alert.drone_type ? `<tr><td>Drone Type:</td><td>${alert.drone_type}</td></tr>` : ''}
                        </table>
                    </div>
                    
                    ${alert.position ? `
                        <div class="alert-detail-section">
                            <h5>Position</h5>
                            <table class="detail-table">
                                <tr><td>Latitude:</td><td>${alert.position.latitude}</td></tr>
                                <tr><td>Longitude:</td><td>${alert.position.longitude}</td></tr>
                                <tr><td>Altitude:</td><td>${alert.position.altitude} m</td></tr>
                            </table>
                        </div>
                    ` : ''}
                    
                    ${alert.metadata ? `
                        <div class="alert-detail-section">
                            <h5>Additional Data</h5>
                            <pre>${JSON.stringify(alert.metadata, null, 2)}</pre>
                        </div>
                    ` : ''}
                </div>
                <div class="modal-footer">
                    ${!this.acknowledgedAlerts.has(alert.id) ? '<button id="modalAcknowledge" class="btn btn-primary">Acknowledge</button>' : ''}
                    <button id="modalResolve" class="btn btn-success">Resolve</button>
                    ${(alert.escalation_level || 0) < 3 ? '<button id="modalEscalate" class="btn btn-warning">Escalate</button>' : ''}
                    <button class="btn btn-secondary modal-close">Close</button>
                </div>
            </div>
        `;
        
        return modal;
    }
    
    /**
     * Show alert history
     */
    showAlertHistory() {
        // Navigate to alerts page or open history modal
        if (typeof window.DroneDetector !== 'undefined') {
            window.DroneDetector.navigateTo('alerts');
        }
    }
    
    // ========================================================================
    // Utility Methods
    // ========================================================================
    
    /**
     * Get alert icon based on severity
     * @param {string} severity - Alert severity
     * @returns {string} FontAwesome icon class
     */
    getAlertIcon(severity) {
        const icons = {
            'CRITICAL': 'fa-skull-crossbones',
            'HIGH': 'fa-exclamation-triangle',
            'MEDIUM': 'fa-exclamation-circle',
            'LOW': 'fa-info-circle',
            'INFO': 'fa-bell'
        };
        return icons[severity?.toUpperCase()] || icons.INFO;
    }
    
    /**
     * Format relative time
     * @param {string} timestamp - ISO timestamp
     * @returns {string} Relative time string
     */
    formatRelativeTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = Math.floor((now - date) / 1000);
        
        if (diff < 60) return 'just now';
        if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
        return `${Math.floor(diff / 86400)} days ago`;
    }
    
    /**
     * Escape HTML to prevent XSS
     * @param {string} str - String to escape
     * @returns {string} Escaped string
     */
    escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
    
    /**
     * Get current alerts
     * @returns {Array} Active alerts
     */
    getActiveAlerts() {
        return [...this.activeAlerts];
    }
    
    /**
     * Get alert count by severity
     * @returns {Object} Alert counts
     */
    getAlertCounts() {
        return {
            critical: this.activeAlerts.filter(a => a.severity === 'CRITICAL').length,
            high: this.activeAlerts.filter(a => a.severity === 'HIGH').length,
            medium: this.activeAlerts.filter(a => a.severity === 'MEDIUM').length,
            low: this.activeAlerts.filter(a => a.severity === 'LOW').length
        };
    }
    
    /**
     * Destroy alert manager
     */
    destroy() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        if (this.ws) {
            this.ws.unsubscribe('alert');
            this.ws.unsubscribe('alert_update');
        }
    }
}

// ============================================================================
// Export for module systems
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = AlertManager;
}

if (typeof window !== 'undefined') {
    window.AlertManager = AlertManager;
}

// ============================================================================
// Auto-initialize
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize alert manager if container exists
    if (document.getElementById('alertsContainer')) {
        window.alertManager = new AlertManager({
            soundEnabled: localStorage.getItem('alertSoundEnabled') !== 'false',
            notificationsEnabled: true,
            autoAcknowledge: false
        });
    }
});