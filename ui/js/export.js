/**
 * Drone Detection System - Data Export Module
 * Version: 2.0.0
 * 
 * This module provides comprehensive data export capabilities,
 * including CSV, JSON, Excel, and PDF exports with customizable
 * field selection, filtering, and formatting options.
 */

// ============================================================================
// Export Manager Class
// ============================================================================

class ExportManager {
    /**
     * Create a new export manager
     * @param {Object} options - Configuration options
     */
    constructor(options = {}) {
        this.apiBase = options.apiBase || '/api';
        this.maxRows = options.maxRows || 100000;
        this.chunkSize = options.chunkSize || 10000;
        this.defaultFormat = options.defaultFormat || 'csv';
        
        // Export options
        this.currentOptions = {
            format: this.defaultFormat,
            fields: [],
            filters: {},
            dateRange: { start: null, end: null },
            includeMetadata: true,
            includeHeaders: true,
            formatDates: true,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
        
        // Available export formats
        this.formats = {
            csv: { name: 'CSV', extension: 'csv', mimeType: 'text/csv' },
            json: { name: 'JSON', extension: 'json', mimeType: 'application/json' },
            excel: { name: 'Excel', extension: 'xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
            pdf: { name: 'PDF', extension: 'pdf', mimeType: 'application/pdf' },
            html: { name: 'HTML', extension: 'html', mimeType: 'text/html' }
        };
        
        // Field definitions
        this.availableFields = this.getAvailableFields();
        
        this.init();
    }
    
    /**
     * Initialize export manager
     */
    init() {
        this.createExportUI();
        this.setupEventListeners();
        this.loadSavedOptions();
    }
    
    /**
     * Create export UI components
     */
    createExportUI() {
        // Create export modal if it doesn't exist
        if (!document.getElementById('exportModal')) {
            this.createExportModal();
        }
        
        // Create export button if needed
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.showExportDialog());
        }
    }
    
    /**
     * Create export modal dialog
     */
    createExportModal() {
        const modal = document.createElement('div');
        modal.id = 'exportModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 600px;">
                <div class="modal-header">
                    <h3><i class="fas fa-download"></i> Export Data</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="export-options">
                        <div class="form-group">
                            <label>Export Format</label>
                            <div class="format-buttons" id="formatButtons">
                                <button data-format="csv" class="format-btn active">CSV</button>
                                <button data-format="json" class="format-btn">JSON</button>
                                <button data-format="excel" class="format-btn">Excel</button>
                                <button data-format="pdf" class="format-btn">PDF</button>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>Fields to Export</label>
                            <div class="field-selector" id="fieldSelector">
                                <div class="field-selector-actions">
                                    <button id="selectAllFields" class="btn-link">Select All</button>
                                    <button id="deselectAllFields" class="btn-link">Deselect All</button>
                                </div>
                                <div class="field-list" id="fieldList"></div>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>Date Range</label>
                            <div class="date-range">
                                <input type="datetime-local" id="exportStartDate" placeholder="Start Date">
                                <span>to</span>
                                <input type="datetime-local" id="exportEndDate" placeholder="End Date">
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>Filters</label>
                            <div class="filter-builder" id="filterBuilder">
                                <div class="filter-row">
                                    <select class="filter-field">
                                        <option value="threat_level">Threat Level</option>
                                        <option value="drone_type">Drone Type</option>
                                        <option value="confidence">Confidence</option>
                                    </select>
                                    <select class="filter-operator">
                                        <option value="eq">Equals</option>
                                        <option value="ne">Not Equals</option>
                                        <option value="gt">Greater Than</option>
                                        <option value="lt">Less Than</option>
                                        <option value="contains">Contains</option>
                                    </select>
                                    <input type="text" class="filter-value" placeholder="Value">
                                    <button class="remove-filter btn-icon">×</button>
                                </div>
                            </div>
                            <button id="addFilter" class="btn-link">+ Add Filter</button>
                        </div>
                        
                        <div class="form-group">
                            <label>Options</label>
                            <div class="checkbox-group">
                                <label>
                                    <input type="checkbox" id="includeMetadata" checked>
                                    Include Metadata
                                </label>
                                <label>
                                    <input type="checkbox" id="includeHeaders" checked>
                                    Include Headers
                                </label>
                                <label>
                                    <input type="checkbox" id="formatDates" checked>
                                    Format Dates
                                </label>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>Row Limit</label>
                            <input type="number" id="rowLimit" value="${this.maxRows}" min="1" max="${this.maxRows}" step="1000">
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button id="cancelExport" class="btn btn-secondary">Cancel</button>
                    <button id="confirmExport" class="btn btn-primary">
                        <i class="fas fa-download"></i> Export
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Cache elements
        this.exportModal = modal;
        this.formatButtons = modal.querySelectorAll('.format-btn');
        this.fieldList = modal.querySelector('#fieldList');
        this.filterBuilder = modal.querySelector('#filterBuilder');
        this.exportStartDate = modal.querySelector('#exportStartDate');
        this.exportEndDate = modal.querySelector('#exportEndDate');
        this.includeMetadata = modal.querySelector('#includeMetadata');
        this.includeHeaders = modal.querySelector('#includeHeaders');
        this.formatDates = modal.querySelector('#formatDates');
        this.rowLimit = modal.querySelector('#rowLimit');
        
        // Populate fields
        this.populateFieldList();
        
        // Modal close handlers
        const closeBtn = modal.querySelector('.modal-close');
        const cancelBtn = modal.querySelector('#cancelExport');
        const confirmBtn = modal.querySelector('#confirmExport');
        
        closeBtn.addEventListener('click', () => this.hideExportDialog());
        cancelBtn.addEventListener('click', () => this.hideExportDialog());
        confirmBtn.addEventListener('click', () => this.performExport());
        
        // Format buttons
        this.formatButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                this.formatButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentOptions.format = btn.dataset.format;
            });
        });
        
        // Field selection buttons
        const selectAllBtn = modal.querySelector('#selectAllFields');
        const deselectAllBtn = modal.querySelector('#deselectAllFields');
        
        if (selectAllBtn) selectAllBtn.addEventListener('click', () => this.selectAllFields());
        if (deselectAllBtn) deselectAllBtn.addEventListener('click', () => this.deselectAllFields());
        
        // Add filter button
        const addFilterBtn = modal.querySelector('#addFilter');
        if (addFilterBtn) addFilterBtn.addEventListener('click', () => this.addFilterRow());
    }
    
    /**
     * Populate field selection list
     */
    populateFieldList() {
        if (!this.fieldList) return;
        
        this.fieldList.innerHTML = this.availableFields.map(field => `
            <label class="field-checkbox">
                <input type="checkbox" value="${field.key}" ${field.default ? 'checked' : ''}>
                <span>${field.label}</span>
                <small>${field.description || ''}</small>
            </label>
        `).join('');
    }
    
    /**
     * Get available export fields
     * @returns {Array} Field definitions
     */
    getAvailableFields() {
        return [
            { key: 'id', label: 'ID', description: 'Unique detection identifier', default: true },
            { key: 'timestamp', label: 'Timestamp', description: 'Detection time', default: true },
            { key: 'drone_type', label: 'Drone Type', description: 'Type/model of drone', default: true },
            { key: 'manufacturer', label: 'Manufacturer', description: 'Drone manufacturer', default: false },
            { key: 'confidence', label: 'Confidence', description: 'Detection confidence score', default: true },
            { key: 'threat_level', label: 'Threat Level', description: 'Assessed threat level', default: true },
            { key: 'frequency', label: 'Frequency', description: 'Detected frequency (Hz)', default: true },
            { key: 'signal_strength', label: 'Signal Strength', description: 'Signal strength (dBm)', default: true },
            { key: 'latitude', label: 'Latitude', description: 'GPS latitude', default: false },
            { key: 'longitude', label: 'Longitude', description: 'GPS longitude', default: false },
            { key: 'altitude', label: 'Altitude', description: 'Altitude (meters)', default: false },
            { key: 'speed', label: 'Speed', description: 'Speed (m/s)', default: false },
            { key: 'heading', label: 'Heading', description: 'Direction (degrees)', default: false },
            { key: 'remote_id', label: 'Remote ID', description: 'Remote ID identifier', default: false },
            { key: 'operator_id', label: 'Operator ID', description: 'Operator identifier', default: false },
            { key: 'snr', label: 'SNR', description: 'Signal-to-noise ratio (dB)', default: false },
            { key: 'bandwidth', label: 'Bandwidth', description: 'Signal bandwidth (Hz)', default: false },
            { key: 'modulation', label: 'Modulation', description: 'Modulation type', default: false },
            { key: 'location_name', label: 'Location Name', description: 'Human-readable location', default: false }
        ];
    }
    
    /**
     * Select all fields
     */
    selectAllFields() {
        const checkboxes = this.fieldList?.querySelectorAll('input[type="checkbox"]');
        checkboxes?.forEach(cb => cb.checked = true);
    }
    
    /**
     * Deselect all fields
     */
    deselectAllFields() {
        const checkboxes = this.fieldList?.querySelectorAll('input[type="checkbox"]');
        checkboxes?.forEach(cb => cb.checked = false);
    }
    
    /**
     * Add filter row
     */
    addFilterRow() {
        const filterRow = document.createElement('div');
        filterRow.className = 'filter-row';
        filterRow.innerHTML = `
            <select class="filter-field">
                <option value="threat_level">Threat Level</option>
                <option value="drone_type">Drone Type</option>
                <option value="confidence">Confidence</option>
                <option value="frequency">Frequency</option>
                <option value="signal_strength">Signal Strength</option>
            </select>
            <select class="filter-operator">
                <option value="eq">Equals</option>
                <option value="ne">Not Equals</option>
                <option value="gt">Greater Than</option>
                <option value="lt">Less Than</option>
                <option value="gte">Greater Than or Equal</option>
                <option value="lte">Less Than or Equal</option>
                <option value="contains">Contains</option>
            </select>
            <input type="text" class="filter-value" placeholder="Value">
            <button class="remove-filter btn-icon">×</button>
        `;
        
        const removeBtn = filterRow.querySelector('.remove-filter');
        removeBtn.addEventListener('click', () => filterRow.remove());
        
        this.filterBuilder?.appendChild(filterRow);
    }
    
    /**
     * Gather current export options
     * @returns {Object} Export options
     */
    gatherOptions() {
        // Get selected fields
        const selectedFields = [];
        const checkboxes = this.fieldList?.querySelectorAll('input[type="checkbox"]:checked');
        if (checkboxes) {
            checkboxes.forEach(cb => selectedFields.push(cb.value));
        }
        
        // Get filters
        const filters = [];
        const filterRows = this.filterBuilder?.querySelectorAll('.filter-row');
        if (filterRows) {
            filterRows.forEach(row => {
                const field = row.querySelector('.filter-field')?.value;
                const operator = row.querySelector('.filter-operator')?.value;
                const value = row.querySelector('.filter-value')?.value;
                if (field && operator && value) {
                    filters.push({ field, operator, value });
                }
            });
        }
        
        return {
            format: this.currentOptions.format,
            fields: selectedFields,
            filters: filters,
            dateRange: {
                start: this.exportStartDate?.value || null,
                end: this.exportEndDate?.value || null
            },
            includeMetadata: this.includeMetadata?.checked || false,
            includeHeaders: this.includeHeaders?.checked || true,
            formatDates: this.formatDates?.checked || true,
            timezone: this.currentOptions.timezone,
            limit: parseInt(this.rowLimit?.value) || this.maxRows
        };
    }
    
    /**
     * Show export dialog
     */
    showExportDialog() {
        if (this.exportModal) {
            this.exportModal.classList.add('active');
        }
    }
    
    /**
     * Hide export dialog
     */
    hideExportDialog() {
        if (this.exportModal) {
            this.exportModal.classList.remove('active');
        }
    }
    
    /**
     * Load saved export options from localStorage
     */
    loadSavedOptions() {
        const saved = localStorage.getItem('exportOptions');
        if (saved) {
            try {
                this.currentOptions = JSON.parse(saved);
            } catch (e) {
                console.error('Failed to load export options:', e);
            }
        }
    }
    
    /**
     * Save export options to localStorage
     */
    saveOptions() {
        localStorage.setItem('exportOptions', JSON.stringify(this.currentOptions));
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Keyboard shortcut: Ctrl+E to open export dialog
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
                e.preventDefault();
                this.showExportDialog();
            }
        });
    }
    
    // ========================================================================
    // Export Methods
    // ========================================================================
    
    /**
     * Perform export based on selected options
     */
    async performExport() {
        const options = this.gatherOptions();
        this.saveOptions();
        this.hideExportDialog();
        
        this.showLoading(true);
        
        try {
            switch (options.format) {
                case 'csv':
                    await this.exportToCSV(options);
                    break;
                case 'json':
                    await this.exportToJSON(options);
                    break;
                case 'excel':
                    await this.exportToExcel(options);
                    break;
                case 'pdf':
                    await this.exportToPDF(options);
                    break;
                default:
                    await this.exportToCSV(options);
            }
            
            this.showToast(`Export completed successfully`, 'success');
        } catch (error) {
            console.error('Export failed:', error);
            this.showToast(`Export failed: ${error.message}`, 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    /**
     * Export to CSV format
     * @param {Object} options - Export options
     */
    async exportToCSV(options) {
        const data = await this.fetchExportData(options);
        
        if (!data || data.length === 0) {
            this.showToast('No data to export', 'warning');
            return;
        }
        
        // Convert to CSV
        const csv = this.convertToCSV(data, options);
        
        // Download
        this.downloadFile(csv, `detections_${this.getDateString()}.csv`, 'text/csv');
    }
    
    /**
     * Export to JSON format
     * @param {Object} options - Export options
     */
    async exportToJSON(options) {
        const data = await this.fetchExportData(options);
        
        if (!data || data.length === 0) {
            this.showToast('No data to export', 'warning');
            return;
        }
        
        const exportData = options.includeMetadata ? {
            metadata: {
                exportDate: new Date().toISOString(),
                version: '2.0.0',
                count: data.length,
                filters: options.filters,
                dateRange: options.dateRange
            },
            data: data
        } : data;
        
        const json = JSON.stringify(exportData, null, 2);
        this.downloadFile(json, `detections_${this.getDateString()}.json`, 'application/json');
    }
    
    /**
     * Export to Excel format
     * @param {Object} options - Export options
     */
    async exportToExcel(options) {
        const data = await this.fetchExportData(options);
        
        if (!data || data.length === 0) {
            this.showToast('No data to export', 'warning');
            return;
        }
        
        // Check if XLSX library is available
        if (typeof XLSX === 'undefined') {
            this.loadExcelLibrary().then(() => this.exportToExcel(options));
            return;
        }
        
        // Convert data to worksheet
        const worksheet = XLSX.utils.json_to_sheet(data);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, 'Detections');
        
        // Add metadata sheet if requested
        if (options.includeMetadata) {
            const metadata = [
                ['Export Date', new Date().toISOString()],
                ['Version', '2.0.0'],
                ['Total Records', data.length],
                ['Filters', JSON.stringify(options.filters)],
                ['Date Range', `${options.dateRange.start || 'All'} to ${options.dateRange.end || 'All'}`]
            ];
            const metadataSheet = XLSX.utils.aoa_to_sheet(metadata);
            XLSX.utils.book_append_sheet(workbook, metadataSheet, 'Metadata');
        }
        
        // Write file
        XLSX.writeFile(workbook, `detections_${this.getDateString()}.xlsx`);
    }
    
    /**
     * Export to PDF format
     * @param {Object} options - Export options
     */
    async exportToPDF(options) {
        const data = await this.fetchExportData(options);
        
        if (!data || data.length === 0) {
            this.showToast('No data to export', 'warning');
            return;
        }
        
        // Check if jspdf is available
        if (typeof window.jspdf === 'undefined') {
            await this.loadPDFLibrary();
        }
        
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
        
        // Add title
        doc.setFontSize(18);
        doc.text('Drone Detection Report', 14, 20);
        doc.setFontSize(10);
        doc.text(`Generated: ${new Date().toLocaleString()}`, 14, 30);
        doc.text(`Total Records: ${data.length}`, 14, 37);
        
        // Create table
        const headers = options.fields.map(field => this.getFieldLabel(field));
        const rows = data.map(row => options.fields.map(field => this.formatValue(row[field], options)));
        
        // AutoTable plugin
        if (doc.autoTable) {
            doc.autoTable({
                head: [headers],
                body: rows,
                startY: 45,
                theme: 'striped',
                styles: { fontSize: 8, cellPadding: 2 },
                headStyles: { fillColor: [79, 172, 254] }
            });
        }
        
        doc.save(`detections_${this.getDateString()}.pdf`);
    }
    
    /**
     * Fetch data for export
     * @param {Object} options - Export options
     * @returns {Promise<Array>} Data array
     */
    async fetchExportData(options) {
        const params = new URLSearchParams();
        
        params.append('limit', options.limit);
        params.append('fields', options.fields.join(','));
        
        if (options.dateRange.start) {
            params.append('start_date', options.dateRange.start);
        }
        if (options.dateRange.end) {
            params.append('end_date', options.dateRange.end);
        }
        
        options.filters.forEach((filter, index) => {
            params.append(`filter[${index}][field]`, filter.field);
            params.append(`filter[${index}][operator]`, filter.operator);
            params.append(`filter[${index}][value]`, filter.value);
        });
        
        const response = await fetch(`${this.apiBase}/export/data?${params.toString()}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        return result.data || [];
    }
    
    /**
     * Convert data to CSV format
     * @param {Array} data - Data array
     * @param {Object} options - Export options
     * @returns {string} CSV string
     */
    convertToCSV(data, options) {
        if (!data || data.length === 0) return '';
        
        const fields = options.fields;
        const rows = [];
        
        // Add headers
        if (options.includeHeaders) {
            rows.push(fields.map(field => this.escapeCSV(this.getFieldLabel(field))).join(','));
        }
        
        // Add data rows
        data.forEach(row => {
            const values = fields.map(field => {
                let value = row[field];
                value = this.formatValue(value, options);
                return this.escapeCSV(String(value || ''));
            });
            rows.push(values.join(','));
        });
        
        return rows.join('\n');
    }
    
    /**
     * Escape CSV value
     * @param {string} value - Value to escape
     * @returns {string} Escaped value
     */
    escapeCSV(value) {
        if (value.includes(',') || value.includes('"') || value.includes('\n')) {
            value = '"' + value.replace(/"/g, '""') + '"';
        }
        return value;
    }
    
    /**
     * Format value for export
     * @param {any} value - Value to format
     * @param {Object} options - Export options
     * @returns {any} Formatted value
     */
    formatValue(value, options) {
        if (value === null || value === undefined) return '';
        
        if (options.formatDates && value instanceof Date) {
            return value.toLocaleString();
        }
        
        if (typeof value === 'object') {
            return JSON.stringify(value);
        }
        
        if (typeof value === 'number') {
            return value;
        }
        
        return value;
    }
    
    /**
     * Get field display label
     * @param {string} field - Field key
     * @returns {string} Field label
     */
    getFieldLabel(field) {
        const fieldDef = this.availableFields.find(f => f.key === field);
        return fieldDef?.label || field;
    }
    
    /**
     * Get date string for filename
     * @returns {string} Formatted date string
     */
    getDateString() {
        const now = new Date();
        return now.toISOString().slice(0, 19).replace(/:/g, '-');
    }
    
    /**
     * Download file
     * @param {string|Blob} content - File content
     * @param {string} filename - Filename
     * @param {string} mimeType - MIME type
     */
    downloadFile(content, filename, mimeType) {
        const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    /**
     * Load Excel export library (SheetJS)
     * @returns {Promise} Load promise
     */
    loadExcelLibrary() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.sheetjs.com/xlsx-0.20.1/package/dist/xlsx.full.min.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
    
    /**
     * Load PDF export library (jsPDF)
     * @returns {Promise} Load promise
     */
    loadPDFLibrary() {
        return new Promise((resolve, reject) => {
            Promise.all([
                new Promise((res) => {
                    const script = document.createElement('script');
                    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
                    script.onload = res;
                    document.head.appendChild(script);
                }),
                new Promise((res) => {
                    const script = document.createElement('script');
                    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.31/jspdf.plugin.autotable.min.js';
                    script.onload = res;
                    document.head.appendChild(script);
                })
            ]).then(resolve).catch(reject);
        });
    }
    
    // ========================================================================
    // Bulk Export Methods
    // ========================================================================
    
    /**
     * Export selected items
     * @param {Array} ids - Array of item IDs
     * @param {string} format - Export format
     */
    async exportSelected(ids, format = 'csv') {
        if (!ids || ids.length === 0) {
            this.showToast('No items selected', 'warning');
            return;
        }
        
        this.showLoading(true);
        
        try {
            const response = await fetch(`${this.apiBase}/export/selected`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids, format })
            });
            
            const blob = await response.blob();
            this.downloadFile(blob, `selected_${this.getDateString()}.${format}`, this.formats[format].mimeType);
            this.showToast(`Exported ${ids.length} items`, 'success');
        } catch (error) {
            console.error('Export failed:', error);
            this.showToast('Export failed', 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    /**
     * Export current view (with current filters)
     * @param {string} format - Export format
     */
    async exportCurrentView(format = 'csv') {
        this.currentOptions.format = format;
        await this.performExport();
    }
    
    /**
     * Export as scheduled report
     * @param {Object} reportConfig - Report configuration
     */
    async scheduleReport(reportConfig) {
        try {
            const response = await fetch(`${this.apiBase}/export/schedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(reportConfig)
            });
            
            const result = await response.json();
            if (result.success) {
                this.showToast('Report scheduled successfully', 'success');
            }
        } catch (error) {
            console.error('Schedule failed:', error);
            this.showToast('Failed to schedule report', 'error');
        }
    }
    
    // ========================================================================
    // Utility Methods
    // ========================================================================
    
    /**
     * Show loading indicator
     * @param {boolean} show - Show/hide loading
     */
    showLoading(show) {
        const loader = document.getElementById('loadingOverlay');
        if (loader) {
            loader.style.display = show ? 'flex' : 'none';
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
    module.exports = ExportManager;
}

if (typeof window !== 'undefined') {
    window.ExportManager = ExportManager;
}

// ============================================================================
// Auto-initialize
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize export manager if export button exists
    if (document.getElementById('exportBtn')) {
        window.exportManager = new ExportManager();
    }
});