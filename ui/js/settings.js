/**
 * Drone Detection System - Settings Management
 * Version: 2.0.0
 * 
 * This module provides comprehensive settings management capabilities,
 * including user preferences, system configuration, notification settings,
 * hardware configuration, and export/import of settings.
 */

// ============================================================================
// Settings Manager Class
// ============================================================================

class SettingsManager {
    /**
     * Create a new settings manager
     * @param {Object} options - Configuration options
     */
    constructor(options = {}) {
        this.apiBase = options.apiBase || '/api';
        this.storageKey = 'droneDetectorSettings';
        this.autoSave = options.autoSave !== false;
        this.autoSaveDelay = options.autoSaveDelay || 1000;
        
        // Settings categories
        this.categories = {
            general: 'General',
            detection: 'Detection',
            hardware: 'Hardware',
            alerts: 'Alerts',
            notifications: 'Notifications',
            display: 'Display',
            security: 'Security',
            advanced: 'Advanced'
        };
        
        // Default settings
        this.defaultSettings = this.getDefaultSettings();
        
        // Current settings
        this.settings = { ...this.defaultSettings };
        this.originalSettings = {};
        
        // Dirty state tracking
        this.dirtyFields = new Set();
        this.saveTimeout = null;
        
        // Event callbacks
        this.callbacks = {
            onSettingsChange: options.onSettingsChange || null,
            onSettingsSaved: options.onSettingsSaved || null,
            onSettingsReset: options.onSettingsReset || null
        };
        
        this.init();
    }
    
    /**
     * Get default settings
     * @returns {Object} Default settings object
     */
    getDefaultSettings() {
        return {
            // General settings
            general: {
                systemName: 'Drone Detection System',
                language: 'en',
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                dateFormat: 'YYYY-MM-DD HH:mm:ss',
                autoStart: false,
                telemetry: true
            },
            
            // Detection settings
            detection: {
                confidenceThreshold: 0.7,
                snrThreshold: 6,
                minDurationMs: 500,
                mlEnabled: true,
                remoteIdEnabled: true,
                tdoaEnabled: false,
                frequencyBands: [
                    { name: '2.4 GHz', start: 2400000000, end: 2483500000, enabled: true, priority: 'high' },
                    { name: '5.8 GHz', start: 5725000000, end: 5875000000, enabled: true, priority: 'high' },
                    { name: '900 MHz', start: 902000000, end: 928000000, enabled: false, priority: 'low' }
                ],
                droneSignatures: true,
                autoClassify: true,
                suspiciousActivityDetection: true
            },
            
            // Hardware settings
            hardware: {
                deviceType: 'hackrf',
                sampleRate: 10000000,
                centerFreq: 2440000000,
                lnaGain: 16,
                vgaGain: 20,
                ampEnable: false,
                antennaPort: 1,
                antennaType: 'omnidirectional',
                ppmCorrection: 0,
                biasTee: false
            },
            
            // Alert settings
            alerts: {
                criticalThreshold: 0.95,
                highThreshold: 0.85,
                mediumThreshold: 0.7,
                lowThreshold: 0.5,
                escalationEnabled: true,
                escalationLevels: 3,
                autoAcknowledge: false,
                autoAcknowledgeDelay: 30,
                alertRetention: 30
            },
            
            // Notification settings
            notifications: {
                email: {
                    enabled: false,
                    smtpServer: 'smtp.gmail.com',
                    smtpPort: 587,
                    username: '',
                    password: '',
                    fromEmail: '',
                    recipients: []
                },
                sms: {
                    enabled: false,
                    provider: 'twilio',
                    accountSid: '',
                    authToken: '',
                    fromNumber: '',
                    recipients: []
                },
                webhook: {
                    enabled: false,
                    url: '',
                    headers: {}
                },
                soundEnabled: true,
                desktopNotifications: true,
                notificationCooldown: 60
            },
            
            // Display settings
            display: {
                theme: 'dark',
                refreshRate: 5,
                animationsEnabled: true,
                showThreatColors: true,
                mapTileProvider: 'cartodb',
                mapDefaultZoom: 12,
                mapDefaultCenter: { lat: 37.7749, lng: -122.4194 },
                tablePageSize: 20,
                chartAnimations: true,
                compactView: false,
                showGrid: true
            },
            
            // Security settings
            security: {
                apiKeyEnabled: true,
                sessionTimeout: 30,
                rateLimit: 60,
                twoFactorEnabled: false,
                    ipWhitelist: [],
                auditLogging: true,
                dataRetentionDays: 30
            },
            
            // Advanced settings
            advanced: {
                debugMode: false,
                logLevel: 'info',
                maxConcurrentScans: 3,
                bufferSize: 524288,
                enableProfiling: false,
                customConfig: {}
            }
        };
    }
    
    /**
     * Initialize settings manager
     */
    async init() {
        await this.loadSettings();
        this.createSettingsUI();
        this.setupEventListeners();
        this.applySettings();
    }
    
    /**
     * Load settings from server and localStorage
     */
    async loadSettings() {
        try {
            // Load from server
            const response = await fetch(`${this.apiBase}/config`);
            const data = await response.json();
            
            if (data.success && data.data) {
                this.settings = this.mergeSettings(this.defaultSettings, data.data);
            } else {
                // Load from localStorage as fallback
                const saved = localStorage.getItem(this.storageKey);
                if (saved) {
                    const parsed = JSON.parse(saved);
                    this.settings = this.mergeSettings(this.defaultSettings, parsed);
                }
            }
        } catch (error) {
            console.error('Failed to load settings:', error);
            // Use localStorage as fallback
            const saved = localStorage.getItem(this.storageKey);
            if (saved) {
                const parsed = JSON.parse(saved);
                this.settings = this.mergeSettings(this.defaultSettings, parsed);
            }
        }
        
        this.originalSettings = JSON.parse(JSON.stringify(this.settings));
    }
    
    /**
     * Merge settings with defaults
     * @param {Object} defaults - Default settings
     * @param {Object} userSettings - User settings
     * @returns {Object} Merged settings
     */
    mergeSettings(defaults, userSettings) {
        const result = { ...defaults };
        
        for (const category in userSettings) {
            if (result[category]) {
                result[category] = { ...result[category], ...userSettings[category] };
            } else {
                result[category] = userSettings[category];
            }
        }
        
        return result;
    }
    
    /**
     * Save settings to server
     */
    async saveSettings() {
        try {
            const response = await fetch(`${this.apiBase}/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.settings)
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.originalSettings = JSON.parse(JSON.stringify(this.settings));
                this.dirtyFields.clear();
                localStorage.setItem(this.storageKey, JSON.stringify(this.settings));
                this.showToast('Settings saved successfully', 'success');
                
                if (this.callbacks.onSettingsSaved) {
                    this.callbacks.onSettingsSaved(this.settings);
                }
                
                this.applySettings();
            } else {
                this.showToast('Failed to save settings', 'error');
            }
        } catch (error) {
            console.error('Failed to save settings:', error);
            this.showToast('Failed to save settings', 'error');
        }
    }
    
    /**
     * Reset settings to defaults
     */
    resetSettings() {
        if (confirm('Are you sure you want to reset all settings to default values?')) {
            this.settings = JSON.parse(JSON.stringify(this.defaultSettings));
            this.dirtyFields.clear();
            this.renderSettings();
            this.saveSettings();
            this.showToast('Settings reset to defaults', 'success');
            
            if (this.callbacks.onSettingsReset) {
                this.callbacks.onSettingsReset();
            }
        }
    }
    
    /**
     * Apply settings to the application
     */
    applySettings() {
        // Apply theme
        if (this.settings.display.theme === 'dark') {
            document.body.setAttribute('data-theme', 'dark');
        } else {
            document.body.removeAttribute('data-theme');
        }
        
        // Apply animations
        if (!this.settings.display.animationsEnabled) {
            document.body.classList.add('reduce-motion');
        } else {
            document.body.classList.remove('reduce-motion');
        }
        
        // Dispatch settings applied event
        const event = new CustomEvent('settingsApplied', { detail: { settings: this.settings } });
        window.dispatchEvent(event);
    }
    
    // ========================================================================
    // UI Creation
    // ========================================================================
    
    /**
     * Create settings UI
     */
    createSettingsUI() {
        const container = document.getElementById('settingsContainer');
        if (!container) return;
        
        container.innerHTML = `
            <div class="settings-sidebar">
                <div class="settings-nav" id="settingsNav">
                    ${Object.entries(this.categories).map(([key, label]) => `
                        <button class="settings-nav-item ${key === 'general' ? 'active' : ''}" data-category="${key}">
                            <i class="fas ${this.getCategoryIcon(key)}"></i>
                            ${label}
                        </button>
                    `).join('')}
                </div>
            </div>
            <div class="settings-content">
                <div class="settings-panel" id="settingsPanel"></div>
                <div class="settings-actions">
                    <button id="saveSettings" class="btn btn-primary">
                        <i class="fas fa-save"></i> Save Changes
                    </button>
                    <button id="resetSettings" class="btn btn-secondary">
                        <i class="fas fa-undo"></i> Reset to Defaults
                    </button>
                    <button id="exportSettings" class="btn btn-secondary">
                        <i class="fas fa-download"></i> Export
                    </button>
                    <button id="importSettings" class="btn btn-secondary">
                        <i class="fas fa-upload"></i> Import
                    </button>
                </div>
            </div>
        `;
        
        // Cache elements
        this.settingsNav = container.querySelector('#settingsNav');
        this.settingsPanel = container.querySelector('#settingsPanel');
        
        // Setup navigation
        this.settingsNav.querySelectorAll('.settings-nav-item').forEach(item => {
            item.addEventListener('click', () => {
                this.settingsNav.querySelectorAll('.settings-nav-item').forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');
                this.renderSettings(item.dataset.category);
            });
        });
        
        // Setup action buttons
        const saveBtn = container.querySelector('#saveSettings');
        const resetBtn = container.querySelector('#resetSettings');
        const exportBtn = container.querySelector('#exportSettings');
        const importBtn = container.querySelector('#importSettings');
        
        if (saveBtn) saveBtn.addEventListener('click', () => this.saveSettings());
        if (resetBtn) resetBtn.addEventListener('click', () => this.resetSettings());
        if (exportBtn) exportBtn.addEventListener('click', () => this.exportSettings());
        if (importBtn) importBtn.addEventListener('click', () => this.importSettings());
        
        // Render initial category
        this.renderSettings('general');
    }
    
    /**
     * Get category icon
     * @param {string} category - Category key
     * @returns {string} FontAwesome icon class
     */
    getCategoryIcon(category) {
        const icons = {
            general: 'fa-sliders-h',
            detection: 'fa-radar',
            hardware: 'fa-microchip',
            alerts: 'fa-bell',
            notifications: 'fa-envelope',
            display: 'fa-palette',
            security: 'fa-shield-alt',
            advanced: 'fa-code'
        };
        return icons[category] || 'fa-cog';
    }
    
    /**
     * Render settings panel for a category
     * @param {string} category - Category key
     */
    renderSettings(category = 'general') {
        if (!this.settingsPanel) return;
        
        const categorySettings = this.settings[category];
        if (!categorySettings) return;
        
        this.settingsPanel.innerHTML = `
            <h2>${this.categories[category]}</h2>
            <div class="settings-form">
                ${this.renderSettingsFields(category, categorySettings)}
            </div>
        `;
        
        // Attach event listeners to form fields
        this.attachFieldEventListeners(category);
    }
    
    /**
     * Render settings fields for a category
     * @param {string} category - Category key
     * @param {Object} settings - Settings object
     * @returns {string} HTML string
     */
    renderSettingsFields(category, settings) {
        const fieldDefinitions = this.getFieldDefinitions(category);
        
        return fieldDefinitions.map(field => {
            const value = settings[field.key];
            
            switch (field.type) {
                case 'text':
                    return this.renderTextField(field, value);
                case 'number':
                    return this.renderNumberField(field, value);
                case 'password':
                    return this.renderPasswordField(field, value);
                case 'checkbox':
                    return this.renderCheckboxField(field, value);
                case 'select':
                    return this.renderSelectField(field, value);
                case 'range':
                    return this.renderRangeField(field, value);
                case 'color':
                    return this.renderColorField(field, value);
                case 'textarea':
                    return this.renderTextareaField(field, value);
                case 'array':
                    return this.renderArrayField(field, value);
                case 'object':
                    return this.renderObjectField(field, value);
                default:
                    return '';
            }
        }).join('');
    }
    
    /**
     * Get field definitions for a category
     * @param {string} category - Category key
     * @returns {Array} Field definitions
     */
    getFieldDefinitions(category) {
        const definitions = {
            general: [
                { key: 'systemName', label: 'System Name', type: 'text', placeholder: 'Enter system name' },
                { key: 'language', label: 'Language', type: 'select', options: [
                    { value: 'en', label: 'English' },
                    { value: 'es', label: 'Español' },
                    { value: 'fr', label: 'Français' },
                    { value: 'de', label: 'Deutsch' },
                    { value: 'zh', label: '中文' }
                ] },
                { key: 'timezone', label: 'Timezone', type: 'select', options: this.getTimezoneOptions() },
                { key: 'autoStart', label: 'Auto-start on boot', type: 'checkbox' },
                { key: 'telemetry', label: 'Send anonymous usage data', type: 'checkbox' }
            ],
            
            detection: [
                { key: 'confidenceThreshold', label: 'Confidence Threshold', type: 'range', min: 0, max: 1, step: 0.01, suffix: '%', multiplier: 100 },
                { key: 'snrThreshold', label: 'SNR Threshold (dB)', type: 'range', min: 0, max: 30, step: 1 },
                { key: 'minDurationMs', label: 'Minimum Detection Duration (ms)', type: 'number', min: 100, max: 5000, step: 100 },
                { key: 'mlEnabled', label: 'Enable ML Classification', type: 'checkbox' },
                { key: 'remoteIdEnabled', label: 'Enable Remote ID Decoding', type: 'checkbox' },
                { key: 'tdoaEnabled', label: 'Enable TDOA Positioning', type: 'checkbox' },
                { key: 'droneSignatures', label: 'Use Drone Signatures', type: 'checkbox' },
                { key: 'autoClassify', label: 'Auto-classify Detections', type: 'checkbox' },
                { key: 'suspiciousActivityDetection', label: 'Suspicious Activity Detection', type: 'checkbox' }
            ],
            
            hardware: [
                { key: 'deviceType', label: 'Device Type', type: 'select', options: [
                    { value: 'hackrf', label: 'HackRF One' },
                    { value: 'rtlsdr', label: 'RTL-SDR' },
                    { value: 'pluto', label: 'ADALM-PLUTO' },
                    { value: 'mock', label: 'Mock (Testing)' }
                ] },
                { key: 'sampleRate', label: 'Sample Rate (MHz)', type: 'number', min: 1, max: 20, step: 1, multiplier: 1e-6 },
                { key: 'centerFreq', label: 'Center Frequency (GHz)', type: 'number', min: 0.1, max: 6, step: 0.01, multiplier: 1e-9 },
                { key: 'lnaGain', label: 'LNA Gain (dB)', type: 'range', min: 0, max: 40, step: 8 },
                { key: 'vgaGain', label: 'VGA Gain (dB)', type: 'range', min: 0, max: 62, step: 2 },
                { key: 'ampEnable', label: 'Enable RF Amplifier', type: 'checkbox' },
                { key: 'antennaPort', label: 'Antenna Port', type: 'select', options: [
                    { value: 1, label: 'Port 1' }, { value: 2, label: 'Port 2' },
                    { value: 3, label: 'Port 3' }, { value: 4, label: 'Port 4' }
                ] },
                { key: 'ppmCorrection', label: 'PPM Correction', type: 'number', min: -100, max: 100, step: 1 },
                { key: 'biasTee', label: 'Enable Bias-T', type: 'checkbox' }
            ],
            
            alerts: [
                { key: 'criticalThreshold', label: 'Critical Threshold', type: 'range', min: 0, max: 1, step: 0.01, multiplier: 100 },
                { key: 'highThreshold', label: 'High Threshold', type: 'range', min: 0, max: 1, step: 0.01, multiplier: 100 },
                { key: 'mediumThreshold', label: 'Medium Threshold', type: 'range', min: 0, max: 1, step: 0.01, multiplier: 100 },
                { key: 'lowThreshold', label: 'Low Threshold', type: 'range', min: 0, max: 1, step: 0.01, multiplier: 100 },
                { key: 'escalationEnabled', label: 'Enable Alert Escalation', type: 'checkbox' },
                { key: 'escalationLevels', label: 'Escalation Levels', type: 'number', min: 1, max: 5 },
                { key: 'autoAcknowledge', label: 'Auto-acknowledge Alerts', type: 'checkbox' },
                { key: 'autoAcknowledgeDelay', label: 'Auto-acknowledge Delay (seconds)', type: 'number', min: 10, max: 300 },
                { key: 'alertRetention', label: 'Alert Retention (days)', type: 'number', min: 1, max: 365 }
            ],
            
            display: [
                { key: 'theme', label: 'Theme', type: 'select', options: [
                    { value: 'dark', label: 'Dark' },
                    { value: 'light', label: 'Light' }
                ] },
                { key: 'refreshRate', label: 'Dashboard Refresh Rate (seconds)', type: 'number', min: 1, max: 60 },
                { key: 'animationsEnabled', label: 'Enable Animations', type: 'checkbox' },
                { key: 'showThreatColors', label: 'Show Threat Colors', type: 'checkbox' },
                { key: 'tablePageSize', label: 'Table Page Size', type: 'select', options: [
                    { value: 10, label: '10 rows' }, { value: 20, label: '20 rows' },
                    { value: 50, label: '50 rows' }, { value: 100, label: '100 rows' }
                ] },
                { key: 'compactView', label: 'Compact View', type: 'checkbox' },
                { key: 'showGrid', label: 'Show Grid in Charts', type: 'checkbox' }
            ],
            
            security: [
                { key: 'sessionTimeout', label: 'Session Timeout (minutes)', type: 'number', min: 5, max: 480 },
                { key: 'rateLimit', label: 'API Rate Limit (requests/min)', type: 'number', min: 10, max: 1000 },
                { key: 'twoFactorEnabled', label: 'Enable Two-Factor Authentication', type: 'checkbox' },
                { key: 'auditLogging', label: 'Enable Audit Logging', type: 'checkbox' },
                { key: 'dataRetentionDays', label: 'Data Retention (days)', type: 'number', min: 1, max: 365 }
            ],
            
            advanced: [
                { key: 'debugMode', label: 'Debug Mode', type: 'checkbox' },
                { key: 'logLevel', label: 'Log Level', type: 'select', options: [
                    { value: 'debug', label: 'Debug' }, { value: 'info', label: 'Info' },
                    { value: 'warn', label: 'Warning' }, { value: 'error', label: 'Error' }
                ] },
                { key: 'maxConcurrentScans', label: 'Max Concurrent Scans', type: 'number', min: 1, max: 10 },
                { key: 'enableProfiling', label: 'Enable Performance Profiling', type: 'checkbox' }
            ]
        };
        
        // Add notification fields dynamically
        if (category === 'notifications') {
            return this.renderNotificationFields();
        }
        
        return definitions[category] || [];
    }
    
    /**
     * Render notification settings (complex)
     * @returns {string} HTML string
     */
    renderNotificationFields() {
        const email = this.settings.notifications.email;
        const sms = this.settings.notifications.sms;
        const webhook = this.settings.notifications.webhook;
        
        return `
            <div class="settings-section">
                <h3>Email Notifications</h3>
                <div class="form-group">
                    <label class="toggle-label">
                        <input type="checkbox" id="emailEnabled" ${email.enabled ? 'checked' : ''}>
                        <span>Enable Email Notifications</span>
                    </label>
                </div>
                <div class="email-settings" style="display: ${email.enabled ? 'block' : 'none'}">
                    <div class="form-group">
                        <label>SMTP Server</label>
                        <input type="text" id="smtpServer" value="${email.smtpServer}">
                    </div>
                    <div class="form-group">
                        <label>SMTP Port</label>
                        <input type="number" id="smtpPort" value="${email.smtpPort}">
                    </div>
                    <div class="form-group">
                        <label>Username</label>
                        <input type="text" id="smtpUsername" value="${email.username}">
                    </div>
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" id="smtpPassword" value="${email.password}">
                    </div>
                    <div class="form-group">
                        <label>From Email</label>
                        <input type="email" id="fromEmail" value="${email.fromEmail}">
                    </div>
                    <div class="form-group">
                        <label>Recipients (comma-separated)</label>
                        <input type="text" id="emailRecipients" value="${email.recipients.join(', ')}">
                    </div>
                </div>
            </div>
            
            <div class="settings-section">
                <h3>SMS Notifications</h3>
                <div class="form-group">
                    <label class="toggle-label">
                        <input type="checkbox" id="smsEnabled" ${sms.enabled ? 'checked' : ''}>
                        <span>Enable SMS Notifications</span>
                    </label>
                </div>
                <div class="sms-settings" style="display: ${sms.enabled ? 'block' : 'none'}">
                    <div class="form-group">
                        <label>Provider</label>
                        <select id="smsProvider">
                            <option value="twilio" ${sms.provider === 'twilio' ? 'selected' : ''}>Twilio</option>
                            <option value="aws" ${sms.provider === 'aws' ? 'selected' : ''}>AWS SNS</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Account SID</label>
                        <input type="text" id="smsAccountSid" value="${sms.accountSid}">
                    </div>
                    <div class="form-group">
                        <label>Auth Token</label>
                        <input type="password" id="smsAuthToken" value="${sms.authToken}">
                    </div>
                    <div class="form-group">
                        <label>From Number</label>
                        <input type="text" id="smsFromNumber" value="${sms.fromNumber}">
                    </div>
                    <div class="form-group">
                        <label>Recipients (comma-separated)</label>
                        <input type="text" id="smsRecipients" value="${sms.recipients.join(', ')}">
                    </div>
                </div>
            </div>
            
            <div class="settings-section">
                <h3>Webhook Notifications</h3>
                <div class="form-group">
                    <label class="toggle-label">
                        <input type="checkbox" id="webhookEnabled" ${webhook.enabled ? 'checked' : ''}>
                        <span>Enable Webhook Notifications</span>
                    </label>
                </div>
                <div class="webhook-settings" style="display: ${webhook.enabled ? 'block' : 'none'}">
                    <div class="form-group">
                        <label>Webhook URL</label>
                        <input type="url" id="webhookUrl" value="${webhook.url}">
                    </div>
                </div>
            </div>
            
            <div class="settings-section">
                <h3>General Notification Settings</h3>
                <div class="form-group">
                    <label class="toggle-label">
                        <input type="checkbox" id="soundEnabled" ${this.settings.notifications.soundEnabled ? 'checked' : ''}>
                        <span>Enable Sound Alerts</span>
                    </label>
                </div>
                <div class="form-group">
                    <label class="toggle-label">
                        <input type="checkbox" id="desktopNotifications" ${this.settings.notifications.desktopNotifications ? 'checked' : ''}>
                        <span>Enable Desktop Notifications</span>
                    </label>
                </div>
                <div class="form-group">
                    <label>Notification Cooldown (seconds)</label>
                    <input type="number" id="notificationCooldown" value="${this.settings.notifications.notificationCooldown}">
                </div>
            </div>
        `;
    }
    
    /**
     * Render text field
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderTextField(field, value) {
        return `
            <div class="form-group">
                <label>${field.label}</label>
                <input type="text" id="${field.key}" value="${value}" placeholder="${field.placeholder || ''}">
            </div>
        `;
    }
    
    /**
     * Render number field
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderNumberField(field, value) {
        let displayValue = value;
        if (field.multiplier) {
            displayValue = value / field.multiplier;
        }
        return `
            <div class="form-group">
                <label>${field.label}</label>
                <input type="number" id="${field.key}" value="${displayValue}" 
                       min="${field.min}" max="${field.max}" step="${field.step || 1}">
                ${field.suffix ? `<span class="field-suffix">${field.suffix}</span>` : ''}
            </div>
        `;
    }
    
    /**
     * Render password field
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderPasswordField(field, value) {
        return `
            <div class="form-group">
                <label>${field.label}</label>
                <input type="password" id="${field.key}" value="${value}" placeholder="${field.placeholder || ''}">
            </div>
        `;
    }
    
    /**
     * Render checkbox field
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderCheckboxField(field, value) {
        return `
            <div class="form-group">
                <label class="toggle-label">
                    <input type="checkbox" id="${field.key}" ${value ? 'checked' : ''}>
                    <span>${field.label}</span>
                </label>
            </div>
        `;
    }
    
    /**
     * Render select field
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderSelectField(field, value) {
        return `
            <div class="form-group">
                <label>${field.label}</label>
                <select id="${field.key}">
                    ${field.options.map(opt => `
                        <option value="${opt.value}" ${value == opt.value ? 'selected' : ''}>${opt.label}</option>
                    `).join('')}
                </select>
            </div>
        `;
    }
    
    /**
     * Render range field
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderRangeField(field, value) {
        let displayValue = value;
        if (field.multiplier) {
            displayValue = value * field.multiplier;
        }
        return `
            <div class="form-group">
                <label>${field.label}: <span id="${field.key}Value">${displayValue}${field.suffix || ''}</span></label>
                <input type="range" id="${field.key}" value="${displayValue}" 
                       min="${field.min}" max="${field.max}" step="${field.step}">
            </div>
        `;
    }
    
    /**
     * Render color field
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderColorField(field, value) {
        return `
            <div class="form-group">
                <label>${field.label}</label>
                <input type="color" id="${field.key}" value="${value}">
            </div>
        `;
    }
    
    /**
     * Render textarea field
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderTextareaField(field, value) {
        return `
            <div class="form-group">
                <label>${field.label}</label>
                <textarea id="${field.key}" rows="3">${value}</textarea>
            </div>
        `;
    }
    
    /**
     * Render array field (simplified)
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderArrayField(field, value) {
        return `
            <div class="form-group">
                <label>${field.label}</label>
                <textarea id="${field.key}" rows="3">${JSON.stringify(value, null, 2)}</textarea>
                <small>JSON format</small>
            </div>
        `;
    }
    
    /**
     * Render object field (simplified)
     * @param {Object} field - Field definition
     * @param {any} value - Field value
     * @returns {string} HTML string
     */
    renderObjectField(field, value) {
        return `
            <div class="form-group">
                <label>${field.label}</label>
                <textarea id="${field.key}" rows="4">${JSON.stringify(value, null, 2)}</textarea>
                <small>JSON format</small>
            </div>
        `;
    }
    
    /**
     * Attach event listeners to form fields
     * @param {string} category - Category key
     */
    attachFieldEventListeners(category) {
        const categorySettings = this.settings[category];
        
        for (const key in categorySettings) {
            const element = document.getElementById(key);
            if (element) {
                const originalHandler = element.onchange;
                element.onchange = (e) => {
                    this.updateSetting(category, key, e.target);
                };
            }
        }
        
        // Handle notification toggles separately
        if (category === 'notifications') {
            this.attachNotificationListeners();
        }
    }
    
    /**
     * Attach notification-specific listeners
     */
    attachNotificationListeners() {
        // Email toggle
        const emailEnabled = document.getElementById('emailEnabled');
        const emailSettings = document.querySelector('.email-settings');
        if (emailEnabled) {
            emailEnabled.onchange = () => {
                emailSettings.style.display = emailEnabled.checked ? 'block' : 'none';
                this.updateSetting('notifications', 'email', { enabled: emailEnabled.checked });
            };
        }
        
        // SMS toggle
        const smsEnabled = document.getElementById('smsEnabled');
        const smsSettings = document.querySelector('.sms-settings');
        if (smsEnabled) {
            smsEnabled.onchange = () => {
                smsSettings.style.display = smsEnabled.checked ? 'block' : 'none';
                this.updateSetting('notifications', 'sms', { enabled: smsEnabled.checked });
            };
        }
        
        // Webhook toggle
        const webhookEnabled = document.getElementById('webhookEnabled');
        const webhookSettings = document.querySelector('.webhook-settings');
        if (webhookEnabled) {
            webhookEnabled.onchange = () => {
                webhookSettings.style.display = webhookEnabled.checked ? 'block' : 'none';
                this.updateSetting('notifications', 'webhook', { enabled: webhookEnabled.checked });
            };
        }
        
        // Email fields
        const emailFields = ['smtpServer', 'smtpPort', 'smtpUsername', 'smtpPassword', 'fromEmail', 'emailRecipients'];
        emailFields.forEach(fieldId => {
            const element = document.getElementById(fieldId);
            if (element) {
                element.onchange = () => {
                    if (fieldId === 'emailRecipients') {
                        this.updateSetting('notifications', 'email', { recipients: element.value.split(',').map(s => s.trim()) });
                    } else {
                        this.updateSetting('notifications', 'email', { [fieldId]: element.value });
                    }
                };
            }
        });
        
        // SMS fields
        const smsFields = ['smsProvider', 'smsAccountSid', 'smsAuthToken', 'smsFromNumber', 'smsRecipients'];
        smsFields.forEach(fieldId => {
            const element = document.getElementById(fieldId);
            if (element) {
                element.onchange = () => {
                    if (fieldId === 'smsRecipients') {
                        this.updateSetting('notifications', 'sms', { recipients: element.value.split(',').map(s => s.trim()) });
                    } else if (fieldId === 'smsProvider') {
                        this.updateSetting('notifications', 'sms', { provider: element.value });
                    } else {
                        this.updateSetting('notifications', 'sms', { [fieldId.replace('sms', '').toLowerCase()]: element.value });
                    }
                };
            }
        });
        
        // Webhook URL
        const webhookUrl = document.getElementById('webhookUrl');
        if (webhookUrl) {
            webhookUrl.onchange = () => {
                this.updateSetting('notifications', 'webhook', { url: webhookUrl.value });
            };
        }
        
        // General notification settings
        const soundEnabled = document.getElementById('soundEnabled');
        if (soundEnabled) {
            soundEnabled.onchange = () => {
                this.updateSetting('notifications', 'soundEnabled', soundEnabled.checked);
            };
        }
        
        const desktopNotifications = document.getElementById('desktopNotifications');
        if (desktopNotifications) {
            desktopNotifications.onchange = () => {
                this.updateSetting('notifications', 'desktopNotifications', desktopNotifications.checked);
            };
        }
        
        const notificationCooldown = document.getElementById('notificationCooldown');
        if (notificationCooldown) {
            notificationCooldown.onchange = () => {
                this.updateSetting('notifications', 'notificationCooldown', parseInt(notificationCooldown.value));
            };
        }
    }
    
    /**
     * Update a setting value
     * @param {string} category - Category key
     * @param {string} key - Setting key
     * @param {any} value - New value
     */
    updateSetting(category, key, value) {
        // Handle nested objects
        if (typeof value === 'object' && !(value instanceof HTMLElement)) {
            this.settings[category][key] = { ...this.settings[category][key], ...value };
        } else if (value instanceof HTMLElement) {
            const element = value;
            let newValue;
            
            if (element.type === 'checkbox') {
                newValue = element.checked;
            } else if (element.type === 'number') {
                newValue = parseFloat(element.value);
                // Apply multiplier if needed
                const fieldDef = this.getFieldDefinitions(category).find(f => f.key === key);
                if (fieldDef && fieldDef.multiplier) {
                    newValue *= fieldDef.multiplier;
                }
            } else if (element.type === 'range') {
                newValue = parseFloat(element.value);
                const displaySpan = document.getElementById(`${key}Value`);
                if (displaySpan) {
                    const fieldDef = this.getFieldDefinitions(category).find(f => f.key === key);
                    displaySpan.textContent = `${element.value}${fieldDef?.suffix || ''}`;
                }
                if (fieldDef && fieldDef.multiplier) {
                    newValue /= fieldDef.multiplier;
                }
            } else {
                newValue = element.value;
            }
            
            this.settings[category][key] = newValue;
        } else {
            this.settings[category][key] = value;
        }
        
        // Mark as dirty
        this.dirtyFields.add(`${category}.${key}`);
        
        // Auto-save if enabled
        if (this.autoSave) {
            if (this.saveTimeout) clearTimeout(this.saveTimeout);
            this.saveTimeout = setTimeout(() => this.saveSettings(), this.autoSaveDelay);
        }
        
        // Trigger change callback
        if (this.callbacks.onSettingsChange) {
            this.callbacks.onSettingsChange(category, key, this.settings[category][key]);
        }
    }
    
    /**
     * Get timezone options for select
     * @returns {Array} Timezone options
     */
    getTimezoneOptions() {
        // Common timezones
        return [
            { value: 'UTC', label: 'UTC' },
            { value: 'America/New_York', label: 'Eastern Time' },
            { value: 'America/Chicago', label: 'Central Time' },
            { value: 'America/Denver', label: 'Mountain Time' },
            { value: 'America/Los_Angeles', label: 'Pacific Time' },
            { value: 'Europe/London', label: 'GMT' },
            { value: 'Europe/Berlin', label: 'CET' },
            { value: 'Asia/Tokyo', label: 'JST' },
            { value: 'Asia/Shanghai', label: 'CST' },
            { value: 'Australia/Sydney', label: 'AEDT' }
        ];
    }
    
    /**
     * Export settings to file
     */
    exportSettings() {
        const dataStr = JSON.stringify(this.settings, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `drone_settings_${new Date().toISOString().slice(0, 19)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.showToast('Settings exported', 'success');
    }
    
    /**
     * Import settings from file
     */
    importSettings() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const imported = JSON.parse(event.target.result);
                    this.settings = this.mergeSettings(this.defaultSettings, imported);
                    this.dirtyFields.clear();
                    this.renderSettings();
                    this.saveSettings();
                    this.showToast('Settings imported successfully', 'success');
                } catch (error) {
                    this.showToast('Invalid settings file', 'error');
                }
            };
            reader.readAsText(file);
        };
        input.click();
    }
    
    /**
     * Get current settings
     * @returns {Object} Current settings
     */
    getSettings() {
        return JSON.parse(JSON.stringify(this.settings));
    }
    
    /**
     * Get specific setting value
     * @param {string} path - Setting path (e.g., 'general.language')
     * @returns {any} Setting value
     */
    getSetting(path) {
        const parts = path.split('.');
        let value = this.settings;
        for (const part of parts) {
            if (value === undefined) return undefined;
            value = value[part];
        }
        return value;
    }
    
    /**
     * Update specific setting
     * @param {string} path - Setting path
     * @param {any} value - New value
     */
    setSetting(path, value) {
        const parts = path.split('.');
        let target = this.settings;
        for (let i = 0; i < parts.length - 1; i++) {
            if (!target[parts[i]]) target[parts[i]] = {};
            target = target[parts[i]];
        }
        target[parts[parts.length - 1]] = value;
        this.dirtyFields.add(path);
        
        if (this.autoSave) {
            if (this.saveTimeout) clearTimeout(this.saveTimeout);
            this.saveTimeout = setTimeout(() => this.saveSettings(), this.autoSaveDelay);
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
}

// ============================================================================
// Export for module systems
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = SettingsManager;
}

if (typeof window !== 'undefined') {
    window.SettingsManager = SettingsManager;
}

// ============================================================================
// Auto-initialize
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('settingsContainer')) {
        window.settingsManager = new SettingsManager();
    }
});