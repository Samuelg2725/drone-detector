/**
 * Drone Detection System - UI Controls
 * Version: 2.0.0
 * 
 * This module provides interactive UI controls for the dashboard,
 * including system controls (start/stop), filter controls,
 * view toggles, export buttons, and real-time command sending.
 */

// ============================================================================
// UI Controls Manager
// ============================================================================

class UIControls {
    /**
     * Create a new UI controls manager
     * @param {Object} options - Configuration options
     */
    constructor(options = {}) {
        this.ws = null;
        this.callbacks = {
            onSystemStart: options.onSystemStart || null,
            onSystemStop: options.onSystemStop || null,
            onClearDetections: options.onClearDetections || null,
            onExport: options.onExport || null,
            onSettingsChange: options.onSettingsChange || null
        };
        
        // DOM elements cache
        this.elements = {};
        this.state = {
            systemRunning: false,
            autoRefresh: true,
            currentView: 'dashboard',
            selectedTimeframe: '24h',
            darkMode: true
        };
        
        this.init();
    }
    
    /**
     * Initialize UI controls
     */
    init() {
        this.cacheElements();
        this.attachEventListeners();
        this.loadUserPreferences();
        this.setupWebSocket();
        this.initTooltips();
        this.initKeyboardShortcuts();
    }
    
    /**
     * Cache DOM elements
     */
    cacheElements() {
        const elementIds = [
            'btnStart', 'btnStop', 'btnClear', 'btnExport',
            'btnRefresh', 'btnFullscreen', 'btnSettings',
            'themeToggle', 'autoRefreshToggle', 'viewSelector',
            'timeframeSelect', 'filterPanelToggle', 'sidebarToggle',
            'zoomIn', 'zoomOut', 'resetView'
        ];
        
        elementIds.forEach(id => {
            this.elements[id] = document.getElementById(id);
        });
        
        // Additional elements
        this.elements.statusIndicator = document.querySelector('.status-dot');
        this.elements.statusText = document.getElementById('connectionStatus');
        this.elements.loadingOverlay = document.getElementById('loadingOverlay');
    }
    
    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // System controls
        if (this.elements.btnStart) {
            this.elements.btnStart.addEventListener('click', () => this.startSystem());
        }
        if (this.elements.btnStop) {
            this.elements.btnStop.addEventListener('click', () => this.stopSystem());
        }
        if (this.elements.btnClear) {
            this.elements.btnClear.addEventListener('click', () => this.clearDetections());
        }
        if (this.elements.btnExport) {
            this.elements.btnExport.addEventListener('click', () => this.exportData());
        }
        if (this.elements.btnRefresh) {
            this.elements.btnRefresh.addEventListener('click', () => this.refreshData());
        }
        if (this.elements.btnFullscreen) {
            this.elements.btnFullscreen.addEventListener('click', () => this.toggleFullscreen());
        }
        if (this.elements.btnSettings) {
            this.elements.btnSettings.addEventListener('click', () => this.openSettings());
        }
        
        // Theme toggle
        if (this.elements.themeToggle) {
            this.elements.themeToggle.addEventListener('change', (e) => this.toggleTheme(e.target.checked));
        }
        
        // Auto-refresh toggle
        if (this.elements.autoRefreshToggle) {
            this.elements.autoRefreshToggle.addEventListener('change', (e) => this.setAutoRefresh(e.target.checked));
        }
        
        // View selector
        if (this.elements.viewSelector) {
            this.elements.viewSelector.addEventListener('change', (e) => this.changeView(e.target.value));
        }
        
        // Timeframe selector
        if (this.elements.timeframeSelect) {
            this.elements.timeframeSelect.addEventListener('change', (e) => this.setTimeframe(e.target.value));
        }
        
        // Zoom controls
        if (this.elements.zoomIn) {
            this.elements.zoomIn.addEventListener('click', () => this.zoomIn());
        }
        if (this.elements.zoomOut) {
            this.elements.zoomOut.addEventListener('click', () => this.zoomOut());
        }
        if (this.elements.resetView) {
            this.elements.resetView.addEventListener('click', () => this.resetView());
        }
        
        // Sidebar toggle for mobile
        if (this.elements.sidebarToggle) {
            this.elements.sidebarToggle.addEventListener('click', () => this.toggleSidebar());
        }
        
        // Filter panel toggle
        if (this.elements.filterPanelToggle) {
            this.elements.filterPanelToggle.addEventListener('click', () => this.toggleFilterPanel());
        }
        
        // Window resize handler
        window.addEventListener('resize', debounce(() => this.handleResize(), 250));
        
        // Visibility change (tab focus)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.state.autoRefresh) {
                this.refreshData();
            }
        });
    }
    
    /**
     * Setup WebSocket connection for command sending
     */
    setupWebSocket() {
        if (typeof getWebSocketManager !== 'undefined') {
            this.ws = getWebSocketManager();
            
            this.ws.on('onOpen', () => {
                this.updateConnectionStatus(true);
            });
            
            this.ws.on('onClose', () => {
                this.updateConnectionStatus(false);
            });
        }
    }
    
    /**
     * Initialize tooltips
     */
    initTooltips() {
        const tooltipElements = document.querySelectorAll('[data-tooltip]');
        tooltipElements.forEach(element => {
            const tooltipText = element.getAttribute('data-tooltip');
            if (tooltipText) {
                element.setAttribute('title', tooltipText);
            }
        });
    }
    
    /**
     * Initialize keyboard shortcuts
     */
    initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + S: Start system
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.startSystem();
            }
            // Ctrl/Cmd + E: Stop system
            else if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
                e.preventDefault();
                this.stopSystem();
            }
            // Ctrl/Cmd + R: Refresh
            else if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                this.refreshData();
            }
            // Ctrl/Cmd + D: Clear detections
            else if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
                e.preventDefault();
                this.clearDetections();
            }
            // F11: Fullscreen
            else if (e.key === 'F11') {
                e.preventDefault();
                this.toggleFullscreen();
            }
            // Escape: Close modals / exit fullscreen
            else if (e.key === 'Escape') {
                this.closeModals();
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                }
            }
            // Ctrl/Cmd + F: Focus search
            else if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                this.focusSearch();
            }
        });
    }
    
    /**
     * Load user preferences from localStorage
     */
    loadUserPreferences() {
        const savedPrefs = localStorage.getItem('droneDetectorPrefs');
        if (savedPrefs) {
            try {
                const prefs = JSON.parse(savedPrefs);
                this.state = { ...this.state, ...prefs };
                this.applyPreferences();
            } catch (e) {
                console.error('Failed to load preferences:', e);
            }
        }
    }
    
    /**
     * Save user preferences
     */
    saveUserPreferences() {
        const prefs = {
            autoRefresh: this.state.autoRefresh,
            currentView: this.state.currentView,
            selectedTimeframe: this.state.selectedTimeframe,
            darkMode: this.state.darkMode
        };
        localStorage.setItem('droneDetectorPrefs', JSON.stringify(prefs));
    }
    
    /**
     * Apply saved preferences
     */
    applyPreferences() {
        if (this.elements.autoRefreshToggle) {
            this.elements.autoRefreshToggle.checked = this.state.autoRefresh;
        }
        if (this.elements.viewSelector) {
            this.elements.viewSelector.value = this.state.currentView;
        }
        if (this.elements.timeframeSelect) {
            this.elements.timeframeSelect.value = this.state.selectedTimeframe;
        }
        if (this.elements.themeToggle) {
            this.elements.themeToggle.checked = this.state.darkMode;
        }
        
        this.setAutoRefresh(this.state.autoRefresh);
        this.changeView(this.state.currentView);
        this.setTimeframe(this.state.selectedTimeframe);
        this.toggleTheme(this.state.darkMode);
    }
    
    // ========================================================================
    // System Control Methods
    // ========================================================================
    
    /**
     * Start the detection system
     */
    startSystem() {
        if (this.state.systemRunning) return;
        
        this.showLoading(true);
        
        // Send command via WebSocket
        if (this.ws && this.ws.isConnected()) {
            this.ws.send('start', {});
        }
        
        // Also send to API
        fetch('/api/system/start', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.state.systemRunning = true;
                    this.updateSystemStatus(true);
                    this.showToast('System started successfully', 'success');
                    if (this.callbacks.onSystemStart) this.callbacks.onSystemStart();
                } else {
                    this.showToast('Failed to start system', 'error');
                }
            })
            .catch(error => {
                console.error('Start failed:', error);
                this.showToast('Failed to start system', 'error');
            })
            .finally(() => {
                this.showLoading(false);
            });
    }
    
    /**
     * Stop the detection system
     */
    stopSystem() {
        if (!this.state.systemRunning) return;
        
        this.showLoading(true);
        
        if (this.ws && this.ws.isConnected()) {
            this.ws.send('stop', {});
        }
        
        fetch('/api/system/stop', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.state.systemRunning = false;
                    this.updateSystemStatus(false);
                    this.showToast('System stopped', 'info');
                    if (this.callbacks.onSystemStop) this.callbacks.onSystemStop();
                } else {
                    this.showToast('Failed to stop system', 'error');
                }
            })
            .catch(error => {
                console.error('Stop failed:', error);
                this.showToast('Failed to stop system', 'error');
            })
            .finally(() => {
                this.showLoading(false);
            });
    }
    
    /**
     * Clear all detections
     */
    clearDetections() {
        if (!confirm('Are you sure you want to clear all detections? This action cannot be undone.')) {
            return;
        }
        
        this.showLoading(true);
        
        fetch('/api/detections', { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.showToast('All detections cleared', 'success');
                    if (this.callbacks.onClearDetections) this.callbacks.onClearDetections();
                    this.refreshData();
                } else {
                    this.showToast('Failed to clear detections', 'error');
                }
            })
            .catch(error => {
                console.error('Clear failed:', error);
                this.showToast('Failed to clear detections', 'error');
            })
            .finally(() => {
                this.showLoading(false);
            });
    }
    
    /**
     * Export data
     */
    exportData() {
        const format = this.showExportDialog();
        if (!format) return;
        
        this.showLoading(true);
        
        const params = new URLSearchParams();
        params.append('format', format);
        params.append('timeframe', this.state.selectedTimeframe);
        
        fetch(`/api/export/detections?${params.toString()}`)
            .then(response => response.blob())
            .then(blob => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `detections_${new Date().toISOString()}.${format}`;
                a.click();
                URL.revokeObjectURL(url);
                this.showToast(`Exported as ${format.toUpperCase()}`, 'success');
                if (this.callbacks.onExport) this.callbacks.onExport(format);
            })
            .catch(error => {
                console.error('Export failed:', error);
                this.showToast('Export failed', 'error');
            })
            .finally(() => {
                this.showLoading(false);
            });
    }
    
    /**
     * Refresh all data
     */
    refreshData() {
        this.showLoading(true);
        
        // Dispatch custom event for components to refresh
        const event = new CustomEvent('dataRefresh');
        window.dispatchEvent(event);
        
        // Also fetch fresh data
        Promise.all([
            fetch('/api/detections?limit=100').then(r => r.json()),
            fetch('/api/alerts').then(r => r.json()),
            fetch('/api/system/metrics').then(r => r.json())
        ]).then(() => {
            this.showToast('Data refreshed', 'success');
        }).catch(error => {
            console.error('Refresh failed:', error);
            this.showToast('Refresh failed', 'error');
        }).finally(() => {
            this.showLoading(false);
        });
    }
    
    // ========================================================================
    // View Control Methods
    // ========================================================================
    
    /**
     * Change current view
     * @param {string} view - View name
     */
    changeView(view) {
        this.state.currentView = view;
        
        // Hide all views
        const views = ['dashboard', 'map', 'detections', 'alerts', 'analytics', 'settings'];
        views.forEach(v => {
            const viewElement = document.getElementById(`${v}View`);
            if (viewElement) viewElement.style.display = 'none';
        });
        
        // Show selected view
        const selectedView = document.getElementById(`${view}View`);
        if (selectedView) selectedView.style.display = 'block';
        
        // Update URL hash
        window.location.hash = view;
        
        this.saveUserPreferences();
        
        // Dispatch view change event
        const event = new CustomEvent('viewChange', { detail: { view } });
        window.dispatchEvent(event);
    }
    
    /**
     * Set timeframe for data display
     * @param {string} timeframe - Timeframe value
     */
    setTimeframe(timeframe) {
        this.state.selectedTimeframe = timeframe;
        this.saveUserPreferences();
        
        // Dispatch timeframe change event
        const event = new CustomEvent('timeframeChange', { detail: { timeframe } });
        window.dispatchEvent(event);
        
        this.refreshData();
    }
    
    /**
     * Zoom in on map/chart
     */
    zoomIn() {
        const event = new CustomEvent('zoomIn');
        window.dispatchEvent(event);
    }
    
    /**
     * Zoom out on map/chart
     */
    zoomOut() {
        const event = new CustomEvent('zoomOut');
        window.dispatchEvent(event);
    }
    
    /**
     * Reset view to default
     */
    resetView() {
        const event = new CustomEvent('resetView');
        window.dispatchEvent(event);
        this.showToast('View reset', 'info');
    }
    
    // ========================================================================
    // Theme and Display Controls
    // ========================================================================
    
    /**
     * Toggle dark/light theme
     * @param {boolean} isDark - Dark mode enabled
     */
    toggleTheme(isDark) {
        this.state.darkMode = isDark;
        const theme = isDark ? 'dark' : 'light';
        document.body.setAttribute('data-theme', theme);
        
        // Update Chart.js theme if available
        if (window.chartManager && typeof window.chartManager.setTheme === 'function') {
            window.chartManager.setTheme(theme);
        }
        
        this.saveUserPreferences();
        
        const event = new CustomEvent('themeChange', { detail: { theme } });
        window.dispatchEvent(event);
    }
    
    /**
     * Toggle auto-refresh
     * @param {boolean} enabled - Auto-refresh enabled
     */
    setAutoRefresh(enabled) {
        this.state.autoRefresh = enabled;
        this.saveUserPreferences();
        
        if (enabled) {
            this.startAutoRefreshTimer();
        } else {
            this.stopAutoRefreshTimer();
        }
        
        const event = new CustomEvent('autoRefreshChange', { detail: { enabled } });
        window.dispatchEvent(event);
    }
    
    /**
     * Start auto-refresh timer
     */
    startAutoRefreshTimer() {
        if (this.refreshTimer) clearInterval(this.refreshTimer);
        this.refreshTimer = setInterval(() => {
            if (this.state.autoRefresh && !document.hidden) {
                this.refreshData();
            }
        }, 30000);
    }
    
    /**
     * Stop auto-refresh timer
     */
    stopAutoRefreshTimer() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
    
    /**
     * Toggle fullscreen mode
     */
    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            this.showToast('Fullscreen mode enabled', 'info');
        } else {
            document.exitFullscreen();
            this.showToast('Fullscreen mode exited', 'info');
        }
    }
    
    // ========================================================================
    // UI Helper Methods
    // ========================================================================
    
    /**
     * Toggle sidebar (mobile)
     */
    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            sidebar.classList.toggle('open');
        }
    }
    
    /**
     * Toggle filter panel
     */
    toggleFilterPanel() {
        const filterPanel = document.getElementById('filterPanel');
        if (filterPanel) {
            filterPanel.classList.toggle('collapsed');
            const icon = this.elements.filterPanelToggle?.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-chevron-right');
                icon.classList.toggle('fa-chevron-left');
            }
        }
    }
    
    /**
     * Focus search input
     */
    focusSearch() {
        const searchInput = document.getElementById('detectionSearch');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    /**
     * Open settings modal
     */
    openSettings() {
        // Dispatch event to open settings
        const event = new CustomEvent('openSettings');
        window.dispatchEvent(event);
    }
    
    /**
     * Close all open modals
     */
    closeModals() {
        const modals = document.querySelectorAll('.modal.active');
        modals.forEach(modal => {
            modal.classList.remove('active');
        });
    }
    
    /**
     * Update connection status display
     * @param {boolean} connected - Connection status
     */
    updateConnectionStatus(connected) {
        if (this.elements.statusIndicator) {
            this.elements.statusIndicator.style.background = connected ? '#4caf50' : '#f44336';
        }
        if (this.elements.statusText) {
            this.elements.statusText.textContent = connected ? 'Connected' : 'Disconnected';
        }
    }
    
    /**
     * Update system running status display
     * @param {boolean} running - System running status
     */
    updateSystemStatus(running) {
        const startBtn = this.elements.btnStart;
        const stopBtn = this.elements.btnStop;
        
        if (startBtn) startBtn.disabled = running;
        if (stopBtn) stopBtn.disabled = !running;
        
        // Update status badge if exists
        const systemStatus = document.getElementById('systemStatus');
        if (systemStatus) {
            systemStatus.textContent = running ? 'Running' : 'Stopped';
            systemStatus.className = running ? 'status-running' : 'status-stopped';
        }
    }
    
    /**
     * Handle window resize
     */
    handleResize() {
        // Close sidebar on mobile when resizing to desktop
        if (window.innerWidth > 768) {
            const sidebar = document.getElementById('sidebar');
            if (sidebar) sidebar.classList.remove('open');
        }
        
        // Dispatch resize event for components
        const event = new CustomEvent('windowResize');
        window.dispatchEvent(event);
    }
    
    /**
     * Show loading overlay
     * @param {boolean} show - Show/hide loading
     */
    showLoading(show) {
        if (this.elements.loadingOverlay) {
            this.elements.loadingOverlay.style.display = show ? 'flex' : 'none';
        }
    }
    
    /**
     * Show toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type
     */
    showToast(message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
    
    /**
     * Show export format dialog
     * @returns {string|null} Selected format
     */
    showExportDialog() {
        // Simple prompt - in production use a modal
        const format = prompt('Export format? (csv, json, excel)', 'csv');
        const validFormats = ['csv', 'json', 'excel'];
        return validFormats.includes(format) ? format : null;
    }
    
    // ========================================================================
    // Command Sending
    // ========================================================================
    
    /**
     * Send command to backend
     * @param {string} command - Command name
     * @param {Object} params - Command parameters
     */
    sendCommand(command, params = {}) {
        if (this.ws && this.ws.isConnected()) {
            this.ws.send(command, params);
        } else {
            fetch(`/api/command/${command}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            }).catch(error => console.error('Command failed:', error));
        }
    }
    
    /**
     * Start recording
     * @param {number} duration - Recording duration in seconds
     */
    startRecording(duration = 60) {
        this.sendCommand('start_recording', { duration });
        this.showToast('Recording started', 'success');
    }
    
    /**
     * Stop recording
     */
    stopRecording() {
        this.sendCommand('stop_recording');
        this.showToast('Recording stopped', 'info');
    }
    
    /**
     * Take snapshot
     */
    takeSnapshot() {
        this.sendCommand('take_snapshot');
        this.showToast('Snapshot taken', 'success');
    }
    
    /**
     * Calibrate noise floor
     */
    calibrateNoiseFloor() {
        this.sendCommand('calibrate_noise_floor');
        this.showToast('Noise floor calibration started', 'info');
    }
    
    // ========================================================================
    // Getters and Setters
    // ========================================================================
    
    /**
     * Get system running state
     * @returns {boolean} System running state
     */
    isSystemRunning() {
        return this.state.systemRunning;
    }
    
    /**
     * Get current view
     * @returns {string} Current view name
     */
    getCurrentView() {
        return this.state.currentView;
    }
    
    /**
     * Get selected timeframe
     * @returns {string} Selected timeframe
     */
    getTimeframe() {
        return this.state.selectedTimeframe;
    }
    
    /**
     * Get auto-refresh state
     * @returns {boolean} Auto-refresh enabled
     */
    isAutoRefreshEnabled() {
        return this.state.autoRefresh;
    }
    
    /**
     * Destroy controls manager
     */
    destroy() {
        this.stopAutoRefreshTimer();
        window.removeEventListener('resize', this.handleResize);
    }
}

// ============================================================================
// Filter Controls
// ============================================================================

class FilterControls {
    /**
     * Create filter controls
     * @param {Object} options - Configuration options
     */
    constructor(options = {}) {
        this.container = options.container || document.getElementById('filterContainer');
        this.onFilterChange = options.onFilterChange || null;
        this.filters = {
            threatLevel: [],
            droneType: [],
            dateRange: { start: null, end: null },
            confidence: { min: 0, max: 100 },
            location: null,
            remoteId: null
        };
        
        this.init();
    }
    
    /**
     * Initialize filter controls
     */
    init() {
        this.createFilterUI();
        this.attachEventListeners();
        this.loadFilterOptions();
    }
    
    /**
     * Create filter UI
     */
    createFilterUI() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="filter-group">
                <label class="filter-label">Threat Level</label>
                <div class="filter-checkboxes" id="threatFilterGroup">
                    <label><input type="checkbox" value="critical"> Critical</label>
                    <label><input type="checkbox" value="high"> High</label>
                    <label><input type="checkbox" value="medium"> Medium</label>
                    <label><input type="checkbox" value="low"> Low</label>
                </div>
            </div>
            <div class="filter-group">
                <label class="filter-label">Drone Type</label>
                <select id="droneTypeFilter" class="filter-select">
                    <option value="">All Types</option>
                </select>
            </div>
            <div class="filter-group">
                <label class="filter-label">Confidence Range</label>
                <div class="filter-range">
                    <input type="range" id="confidenceMin" min="0" max="100" value="0">
                    <span id="confidenceMinVal">0%</span>
                    <span> - </span>
                    <input type="range" id="confidenceMax" min="0" max="100" value="100">
                    <span id="confidenceMaxVal">100%</span>
                </div>
            </div>
            <div class="filter-group">
                <label class="filter-label">Date Range</label>
                <div class="filter-date-range">
                    <input type="datetime-local" id="dateStart" placeholder="Start Date">
                    <input type="datetime-local" id="dateEnd" placeholder="End Date">
                </div>
            </div>
            <div class="filter-actions">
                <button id="applyFilters" class="btn btn-primary btn-sm">Apply Filters</button>
                <button id="resetFilters" class="btn btn-outline btn-sm">Reset</button>
            </div>
        `;
        
        // Cache elements
        this.threatCheckboxes = this.container.querySelectorAll('#threatFilterGroup input');
        this.droneTypeSelect = this.container.querySelector('#droneTypeFilter');
        this.confidenceMin = this.container.querySelector('#confidenceMin');
        this.confidenceMax = this.container.querySelector('#confidenceMax');
        this.confidenceMinVal = this.container.querySelector('#confidenceMinVal');
        this.confidenceMaxVal = this.container.querySelector('#confidenceMaxVal');
        this.dateStart = this.container.querySelector('#dateStart');
        this.dateEnd = this.container.querySelector('#dateEnd');
        this.applyBtn = this.container.querySelector('#applyFilters');
        this.resetBtn = this.container.querySelector('#resetFilters');
    }
    
    /**
     * Attach event listeners
     */
    attachEventListeners() {
        if (this.confidenceMin) {
            this.confidenceMin.addEventListener('input', (e) => {
                this.confidenceMinVal.textContent = `${e.target.value}%`;
                this.filters.confidence.min = parseInt(e.target.value);
            });
        }
        
        if (this.confidenceMax) {
            this.confidenceMax.addEventListener('input', (e) => {
                this.confidenceMaxVal.textContent = `${e.target.value}%`;
                this.filters.confidence.max = parseInt(e.target.value);
            });
        }
        
        if (this.applyBtn) {
            this.applyBtn.addEventListener('click', () => this.applyFilters());
        }
        
        if (this.resetBtn) {
            this.resetBtn.addEventListener('click', () => this.resetFilters());
        }
    }
    
    /**
     * Load filter options from API
     */
    async loadFilterOptions() {
        try {
            const response = await fetch('/api/detections/types');
            const data = await response.json();
            if (data.success && data.data) {
                this.droneTypeSelect.innerHTML = '<option value="">All Types</option>' +
                    data.data.map(type => `<option value="${type}">${type}</option>`).join('');
            }
        } catch (error) {
            console.error('Failed to load filter options:', error);
        }
    }
    
    /**
     * Apply filters
     */
    applyFilters() {
        // Get selected threat levels
        const selectedThreats = Array.from(this.threatCheckboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);
        
        this.filters.threatLevel = selectedThreats;
        this.filters.droneType = this.droneTypeSelect?.value || '';
        
        if (this.dateStart?.value) {
            this.filters.dateRange.start = new Date(this.dateStart.value);
        }
        if (this.dateEnd?.value) {
            this.filters.dateRange.end = new Date(this.dateEnd.value);
        }
        
        if (this.onFilterChange) {
            this.onFilterChange(this.filters);
        }
        
        // Dispatch filter change event
        const event = new CustomEvent('filtersChanged', { detail: { filters: this.filters } });
        window.dispatchEvent(event);
    }
    
    /**
     * Reset all filters
     */
    resetFilters() {
        this.threatCheckboxes.forEach(cb => cb.checked = false);
        if (this.droneTypeSelect) this.droneTypeSelect.value = '';
        if (this.confidenceMin) this.confidenceMin.value = 0;
        if (this.confidenceMax) this.confidenceMax.value = 100;
        if (this.confidenceMinVal) this.confidenceMinVal.textContent = '0%';
        if (this.confidenceMaxVal) this.confidenceMaxVal.textContent = '100%';
        if (this.dateStart) this.dateStart.value = '';
        if (this.dateEnd) this.dateEnd.value = '';
        
        this.filters = {
            threatLevel: [],
            droneType: '',
            dateRange: { start: null, end: null },
            confidence: { min: 0, max: 100 },
            location: null,
            remoteId: null
        };
        
        if (this.onFilterChange) {
            this.onFilterChange(this.filters);
        }
    }
    
    /**
     * Get current filters
     * @returns {Object} Filter object
     */
    getFilters() {
        return { ...this.filters };
    }
}

// ============================================================================
// Debounce Utility
// ============================================================================

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ============================================================================
// Export for module systems
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { UIControls, FilterControls };
}

if (typeof window !== 'undefined') {
    window.UIControls = UIControls;
    window.FilterControls = FilterControls;
}

// ============================================================================
// Auto-initialize on DOM ready
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize UI controls if container exists
    if (document.getElementById('btnStart')) {
        window.uiControls = new UIControls();
    }
    
    // Initialize filter controls if container exists
    if (document.getElementById('filterContainer')) {
        window.filterControls = new FilterControls();
    }
});