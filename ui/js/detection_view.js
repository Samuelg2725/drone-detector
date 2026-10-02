/**
 * Drone Detection System - Detection Table View
 * Version: 2.0.0
 * 
 * This module provides an interactive table view for drone detections,
 * including real-time updates, sorting, filtering, pagination, and
 * detailed view expansion.
 */

// ============================================================================
// Detection Table Class
// ============================================================================

class DetectionTableView {
    /**
     * Create a new detection table view
     * @param {Object} options - Configuration options
     * @param {HTMLElement} options.container - Container element
     * @param {Object} options.columns - Column configuration
     * @param {Array} options.sortableColumns - Sortable column names
     * @param {boolean} options.showPagination - Show pagination controls
     * @param {number} options.pageSize - Items per page
     * @param {Function} options.onRowClick - Row click callback
     * @param {Function} options.onSelectionChange - Selection change callback
     */
    constructor(options = {}) {
        this.container = options.container || document.getElementById('detectionsTableContainer');
        this.columns = options.columns || this.getDefaultColumns();
        this.sortableColumns = options.sortableColumns || ['timestamp', 'confidence', 'threat_level', 'frequency'];
        this.showPagination = options.showPagination !== false;
        this.pageSize = options.pageSize || 20;
        this.onRowClick = options.onRowClick || null;
        this.onSelectionChange = options.onSelectionChange || null;
        
        // Data
        this.detections = [];
        this.filteredDetections = [];
        this.currentPage = 1;
        this.sortColumn = 'timestamp';
        this.sortDirection = 'desc';
        this.filters = {
            search: '',
            threatLevel: '',
            droneType: '',
            startDate: null,
            endDate: null,
            minConfidence: 0
        };
        this.selectedRows = new Set();
        this.expandedRows = new Set();
        
        // DOM elements
        this.tableBody = null;
        this.paginationContainer = null;
        this.searchInput = null;
        this.filterPanel = null;
        this.bulkActionsBar = null;
        
        // WebSocket connection for real-time updates
        this.ws = null;
        
        this.init();
    }
    
    // ========================================================================
    // Initialization
    // ========================================================================
    
    /**
     * Initialize the detection table
     */
    init() {
        this.createTableStructure();
        this.createToolbar();
        this.createPagination();
        this.createBulkActionsBar();
        this.setupEventListeners();
        this.setupWebSocket();
        this.loadInitialData();
    }
    
    /**
     * Get default column configuration
     * @returns {Array} Column configuration
     */
    getDefaultColumns() {
        return [
            { key: 'select', label: '', width: '40px', sortable: false },
            { key: 'timestamp', label: 'Time', width: '180px', sortable: true, format: (val) => this.formatTimestamp(val) },
            { key: 'drone_type', label: 'Drone Type', width: '150px', sortable: true },
            { key: 'manufacturer', label: 'Manufacturer', width: '120px', sortable: true },
            { key: 'confidence', label: 'Confidence', width: '100px', sortable: true, format: (val) => this.formatConfidence(val) },
            { key: 'threat_level', label: 'Threat', width: '100px', sortable: true, format: (val) => this.formatThreat(val) },
            { key: 'frequency', label: 'Frequency', width: '120px', sortable: true, format: (val) => this.formatFrequency(val) },
            { key: 'signal_strength', label: 'Signal', width: '100px', sortable: true, format: (val) => this.formatSignal(val) },
            { key: 'location', label: 'Location', width: '150px', sortable: false, format: (val, row) => this.formatLocation(row) },
            { key: 'actions', label: 'Actions', width: '100px', sortable: false }
        ];
    }
    
    /**
     * Create table DOM structure
     */
    createTableStructure() {
        this.container.innerHTML = '';
        
        // Create table wrapper
        const tableWrapper = document.createElement('div');
        tableWrapper.className = 'table-wrapper';
        tableWrapper.style.overflowX = 'auto';
        
        // Create table
        const table = document.createElement('table');
        table.className = 'detection-table';
        
        // Create header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        
        this.columns.forEach(column => {
            const th = document.createElement('th');
            th.className = `col-${column.key}`;
            th.style.width = column.width;
            th.textContent = column.label;
            
            if (column.sortable && this.sortableColumns.includes(column.key)) {
                th.classList.add('sortable');
                th.addEventListener('click', () => this.sortBy(column.key));
                
                // Add sort indicator
                if (this.sortColumn === column.key) {
                    th.classList.add(`sort-${this.sortDirection}`);
                    const icon = document.createElement('span');
                    icon.className = 'sort-icon';
                    icon.innerHTML = this.sortDirection === 'asc' ? '↑' : '↓';
                    th.appendChild(icon);
                }
            }
            
            headerRow.appendChild(th);
        });
        
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Create body
        const tbody = document.createElement('tbody');
        tbody.id = 'detectionsTableBody';
        table.appendChild(tbody);
        this.tableBody = tbody;
        
        tableWrapper.appendChild(table);
        this.container.appendChild(tableWrapper);
    }
    
    /**
     * Create toolbar with search and filters
     */
    createToolbar() {
        const toolbar = document.createElement('div');
        toolbar.className = 'table-toolbar';
        toolbar.innerHTML = `
            <div class="toolbar-left">
                <div class="table-search">
                    <i class="fas fa-search"></i>
                    <input type="text" id="detectionSearch" placeholder="Search detections...">
                </div>
                <div class="table-filter">
                    <select id="threatFilter">
                        <option value="">All Threats</option>
                        <option value="critical">Critical</option>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                    </select>
                </div>
                <div class="table-filter">
                    <select id="droneTypeFilter">
                        <option value="">All Types</option>
                    </select>
                </div>
                <button id="filterBtn" class="btn btn-secondary btn-sm">
                    <i class="fas fa-filter"></i> Filter
                </button>
                <button id="clearFiltersBtn" class="btn btn-outline btn-sm">
                    <i class="fas fa-times"></i> Clear
                </button>
            </div>
            <div class="toolbar-right">
                <button id="refreshBtn" class="btn btn-secondary btn-sm">
                    <i class="fas fa-sync-alt"></i> Refresh
                </button>
                <button id="exportBtn" class="btn btn-secondary btn-sm">
                    <i class="fas fa-download"></i> Export
                </button>
            </div>
        `;
        
        this.container.insertBefore(toolbar, this.container.firstChild);
        
        // Store references
        this.searchInput = toolbar.querySelector('#detectionSearch');
        this.threatFilter = toolbar.querySelector('#threatFilter');
        this.droneTypeFilter = toolbar.querySelector('#droneTypeFilter');
        
        // Setup event listeners
        const filterBtn = toolbar.querySelector('#filterBtn');
        const clearBtn = toolbar.querySelector('#clearFiltersBtn');
        const refreshBtn = toolbar.querySelector('#refreshBtn');
        const exportBtn = toolbar.querySelector('#exportBtn');
        
        if (filterBtn) filterBtn.addEventListener('click', () => this.applyFilters());
        if (clearBtn) clearBtn.addEventListener('click', () => this.clearFilters());
        if (refreshBtn) refreshBtn.addEventListener('click', () => this.refresh());
        if (exportBtn) exportBtn.addEventListener('click', () => this.exportData());
        
        // Search with debounce
        if (this.searchInput) {
            this.searchInput.addEventListener('input', debounce(() => this.applyFilters(), 300));
        }
    }
    
    /**
     * Create pagination controls
     */
    createPagination() {
        if (!this.showPagination) return;
        
        this.paginationContainer = document.createElement('div');
        this.paginationContainer.className = 'table-footer';
        this.container.appendChild(this.paginationContainer);
        this.updatePagination();
    }
    
    /**
     * Create bulk actions bar
     */
    createBulkActionsBar() {
        this.bulkActionsBar = document.createElement('div');
        this.bulkActionsBar.className = 'bulk-actions-bar';
        this.bulkActionsBar.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 12px 24px;
            display: none;
            gap: 16px;
            z-index: 100;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        `;
        this.bulkActionsBar.innerHTML = `
            <span id="selectedCount">0 selected</span>
            <button id="bulkExportBtn" class="btn btn-secondary btn-sm">
                <i class="fas fa-download"></i> Export
            </button>
            <button id="bulkDeleteBtn" class="btn btn-danger btn-sm">
                <i class="fas fa-trash"></i> Delete
            </button>
            <button id="bulkClearBtn" class="btn btn-outline btn-sm">
                <i class="fas fa-times"></i> Clear
            </button>
        `;
        document.body.appendChild(this.bulkActionsBar);
        
        // Setup bulk action listeners
        const bulkExport = this.bulkActionsBar.querySelector('#bulkExportBtn');
        const bulkDelete = this.bulkActionsBar.querySelector('#bulkDeleteBtn');
        const bulkClear = this.bulkActionsBar.querySelector('#bulkClearBtn');
        
        if (bulkExport) bulkExport.addEventListener('click', () => this.exportSelected());
        if (bulkDelete) bulkDelete.addEventListener('click', () => this.deleteSelected());
        if (bulkClear) bulkClear.addEventListener('click', () => this.clearSelection());
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl+A to select all
            if (e.ctrlKey && e.key === 'a') {
                e.preventDefault();
                this.selectAll();
            }
            // Escape to clear selection
            if (e.key === 'Escape') {
                this.clearSelection();
            }
        });
    }
    
    /**
     * Setup WebSocket connection for real-time updates
     */
    setupWebSocket() {
        if (typeof getWebSocketManager !== 'undefined') {
            this.ws = getWebSocketManager();
            this.ws.subscribe('detection', (data) => {
                this.addDetection(data);
            });
            this.ws.subscribe('detection_update', (data) => {
                this.updateDetection(data);
            });
        }
    }
    
    // ========================================================================
    // Data Management
    // ========================================================================
    
    /**
     * Load initial detection data
     */
    async loadInitialData() {
        try {
            const response = await fetch('/api/detections?limit=1000');
            const data = await response.json();
            if (data.success && data.data) {
                this.detections = data.data.items || [];
                this.applyFilters();
                this.updateDroneTypeFilter();
            }
        } catch (error) {
            console.error('Failed to load detections:', error);
            this.showEmptyState();
        }
    }
    
    /**
     * Add a new detection
     * @param {Object} detection - Detection data
     */
    addDetection(detection) {
        this.detections.unshift(detection);
        if (this.detections.length > 10000) {
            this.detections = this.detections.slice(0, 10000);
        }
        this.applyFilters();
        
        // Highlight new row
        const newRow = this.tableBody?.querySelector(`tr[data-id="${detection.id}"]`);
        if (newRow) {
            newRow.classList.add('row-new');
            setTimeout(() => newRow.classList.remove('row-new'), 2000);
        }
    }
    
    /**
     * Update an existing detection
     * @param {Object} detection - Updated detection data
     */
    updateDetection(detection) {
        const index = this.detections.findIndex(d => d.id === detection.id);
        if (index !== -1) {
            this.detections[index] = { ...this.detections[index], ...detection };
            this.applyFilters();
        }
    }
    
    /**
     * Apply all active filters
     */
    applyFilters() {
        this.filteredDetections = this.detections.filter(detection => {
            // Search filter
            if (this.filters.search) {
                const searchTerm = this.filters.search.toLowerCase();
                const matchesSearch = 
                    (detection.drone_type || '').toLowerCase().includes(searchTerm) ||
                    (detection.id || '').toLowerCase().includes(searchTerm) ||
                    (detection.remote_id || '').toLowerCase().includes(searchTerm);
                if (!matchesSearch) return false;
            }
            
            // Threat level filter
            if (this.filters.threatLevel) {
                if ((detection.threat_level || '').toLowerCase() !== this.filters.threatLevel.toLowerCase()) {
                    return false;
                }
            }
            
            // Drone type filter
            if (this.filters.droneType) {
                if ((detection.drone_type || '') !== this.filters.droneType) {
                    return false;
                }
            }
            
            // Date range filter
            if (this.filters.startDate) {
                const detectionDate = new Date(detection.timestamp);
                if (detectionDate < this.filters.startDate) return false;
            }
            if (this.filters.endDate) {
                const detectionDate = new Date(detection.timestamp);
                if (detectionDate > this.filters.endDate) return false;
            }
            
            // Confidence filter
            if ((detection.confidence || 0) < this.filters.minConfidence) return false;
            
            return true;
        });
        
        // Apply sorting
        this.sortDetections();
        
        // Reset to first page
        this.currentPage = 1;
        
        // Update UI
        this.render();
        this.updatePagination();
        this.updateSelectionCount();
    }
    
    /**
     * Sort detections
     */
    sortDetections() {
        this.filteredDetections.sort((a, b) => {
            let aVal = a[this.sortColumn];
            let bVal = b[this.sortColumn];
            
            // Special handling for different types
            if (this.sortColumn === 'timestamp') {
                aVal = new Date(aVal).getTime();
                bVal = new Date(bVal).getTime();
            } else if (this.sortColumn === 'confidence') {
                aVal = aVal || 0;
                bVal = bVal || 0;
            } else if (this.sortColumn === 'frequency') {
                aVal = aVal || 0;
                bVal = bVal || 0;
            }
            
            if (aVal < bVal) return this.sortDirection === 'asc' ? -1 : 1;
            if (aVal > bVal) return this.sortDirection === 'asc' ? 1 : -1;
            return 0;
        });
    }
    
    /**
     * Sort by column
     * @param {string} column - Column key
     */
    sortBy(column) {
        if (this.sortColumn === column) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = column;
            this.sortDirection = 'desc';
        }
        
        this.sortDetections();
        this.render();
        this.updatePagination();
    }
    
    /**
     * Clear all filters
     */
    clearFilters() {
        this.filters = {
            search: '',
            threatLevel: '',
            droneType: '',
            startDate: null,
            endDate: null,
            minConfidence: 0
        };
        
        if (this.searchInput) this.searchInput.value = '';
        if (this.threatFilter) this.threatFilter.value = '';
        if (this.droneTypeFilter) this.droneTypeFilter.value = '';
        
        this.applyFilters();
    }
    
    /**
     * Refresh data from server
     */
    async refresh() {
        await this.loadInitialData();
        this.showToast('Data refreshed', 'success');
    }
    
    // ========================================================================
    // Rendering
    // ========================================================================
    
    /**
     * Render the table
     */
    render() {
        if (!this.tableBody) return;
        
        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;
        const pageDetections = this.filteredDetections.slice(start, end);
        
        if (pageDetections.length === 0) {
            this.showEmptyState();
            return;
        }
        
        this.tableBody.innerHTML = pageDetections.map(detection => this.renderRow(detection)).join('');
        
        // Attach event listeners to new rows
        this.attachRowEventListeners();
    }
    
    /**
     * Render a single row
     * @param {Object} detection - Detection data
     * @returns {string} HTML string
     */
    renderRow(detection) {
        const isSelected = this.selectedRows.has(detection.id);
        const isExpanded = this.expandedRows.has(detection.id);
        const threatClass = this.getThreatClass(detection.threat_level);
        
        return `
            <tr class="detection-row ${threatClass} ${isSelected ? 'selected' : ''}" data-id="${detection.id}">
                ${this.columns.map(column => this.renderCell(detection, column)).join('')}
            </tr>
            ${isExpanded ? this.renderDetailRow(detection) : ''}
        `;
    }
    
    /**
     * Render a table cell
     * @param {Object} detection - Detection data
     * @param {Object} column - Column configuration
     * @returns {string} HTML string
     */
    renderCell(detection, column) {
        let value = detection[column.key];
        
        if (column.format) {
            value = column.format(value, detection);
        }
        
        if (column.key === 'select') {
            return `<td class="col-select">
                <label class="detection-checkbox">
                    <input type="checkbox" data-id="${detection.id}" ${this.selectedRows.has(detection.id) ? 'checked' : ''}>
                    <span class="checkmark"></span>
                </label>
            </td>`;
        }
        
        if (column.key === 'actions') {
            return `<td class="col-actions">
                <button class="action-btn" onclick="window.detectionView?.viewDetails('${detection.id}')">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="action-btn" onclick="window.detectionView?.analyze('${detection.id}')">
                    <i class="fas fa-chart-line"></i>
                </button>
                <button class="action-btn expand-btn" data-id="${detection.id}">
                    <i class="fas ${this.expandedRows.has(detection.id) ? 'fa-chevron-up' : 'fa-chevron-down'}"></i>
                </button>
            </td>`;
        }
        
        return `<td class="col-${column.key}">${value || '-'}</td>`;
    }
    
    /**
     * Render expanded detail row
     * @param {Object} detection - Detection data
     * @returns {string} HTML string
     */
    renderDetailRow(detection) {
        return `
            <tr class="detail-row expanded">
                <td colspan="${this.columns.length}" class="detail-cell">
                    <div class="detail-content">
                        <div class="detail-section">
                            <div class="detail-section-title">Signal Details</div>
                            <div class="detail-item">
                                <span class="detail-label">Frequency:</span>
                                <span class="detail-value">${this.formatFrequency(detection.frequency)}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Bandwidth:</span>
                                <span class="detail-value">${detection.bandwidth ? (detection.bandwidth / 1e6).toFixed(2) + ' MHz' : 'N/A'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">SNR:</span>
                                <span class="detail-value">${detection.snr ? detection.snr.toFixed(1) + ' dB' : 'N/A'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Modulation:</span>
                                <span class="detail-value">${detection.modulation || 'N/A'}</span>
                            </div>
                        </div>
                        <div class="detail-section">
                            <div class="detail-section-title">Position & Tracking</div>
                            <div class="detail-item">
                                <span class="detail-label">Latitude:</span>
                                <span class="detail-value">${detection.latitude ? detection.latitude.toFixed(6) : 'N/A'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Longitude:</span>
                                <span class="detail-value">${detection.longitude ? detection.longitude.toFixed(6) : 'N/A'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Altitude:</span>
                                <span class="detail-value">${detection.altitude ? detection.altitude.toFixed(0) + ' m' : 'N/A'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Speed:</span>
                                <span class="detail-value">${detection.speed ? detection.speed.toFixed(1) + ' m/s' : 'N/A'}</span>
                            </div>
                        </div>
                        <div class="detail-section">
                            <div class="detail-section-title">Remote ID</div>
                            <div class="detail-item">
                                <span class="detail-label">Remote ID:</span>
                                <span class="detail-value">${detection.remote_id || 'Not available'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Operator ID:</span>
                                <span class="detail-value">${detection.operator_id || 'N/A'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">UAS ID:</span>
                                <span class="detail-value">${detection.uas_id || 'N/A'}</span>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }
    
    /**
     * Show empty state
     */
    showEmptyState() {
        if (this.tableBody) {
            this.tableBody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="${this.columns.length}" class="empty-cell">
                        <div class="table-empty">
                            <i class="fas fa-search empty-icon"></i>
                            <div class="empty-title">No detections found</div>
                            <div class="empty-message">Try adjusting your filters or check back later.</div>
                        </div>
                    </td>
                </tr>
            `;
        }
    }
    
    /**
     * Attach event listeners to table rows
     */
    attachRowEventListeners() {
        // Row click for selection
        const rows = this.tableBody.querySelectorAll('.detection-row');
        rows.forEach(row => {
            row.addEventListener('click', (e) => {
                // Don't trigger if clicking on checkbox or action buttons
                if (e.target.type === 'checkbox' || e.target.closest('.action-btn')) return;
                
                const id = row.dataset.id;
                if (this.onRowClick) {
                    this.onRowClick(this.detections.find(d => d.id === id));
                }
            });
        });
        
        // Checkbox change
        const checkboxes = this.tableBody.querySelectorAll('.detection-checkbox input');
        checkboxes.forEach(cb => {
            cb.addEventListener('change', (e) => {
                e.stopPropagation();
                const id = cb.dataset.id;
                if (cb.checked) {
                    this.selectedRows.add(id);
                } else {
                    this.selectedRows.delete(id);
                }
                this.updateRowSelection(id, cb.checked);
                this.updateSelectionCount();
                
                if (this.onSelectionChange) {
                    this.onSelectionChange(Array.from(this.selectedRows));
                }
            });
        });
        
        // Expand buttons
        const expandBtns = this.tableBody.querySelectorAll('.expand-btn');
        expandBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                if (this.expandedRows.has(id)) {
                    this.expandedRows.delete(id);
                } else {
                    this.expandedRows.add(id);
                }
                this.render();
            });
        });
    }
    
    /**
     * Update row selection styling
     * @param {string} id - Detection ID
     * @param {boolean} selected - Selected state
     */
    updateRowSelection(id, selected) {
        const row = this.tableBody.querySelector(`tr[data-id="${id}"]`);
        if (row) {
            if (selected) {
                row.classList.add('selected');
            } else {
                row.classList.remove('selected');
            }
        }
    }
    
    /**
     * Update selection count display
     */
    updateSelectionCount() {
        const count = this.selectedRows.size;
        const countSpan = this.bulkActionsBar?.querySelector('#selectedCount');
        if (countSpan) {
            countSpan.textContent = `${count} selected`;
            this.bulkActionsBar.style.display = count > 0 ? 'flex' : 'none';
        }
    }
    
    /**
     * Select all rows on current page
     */
    selectAll() {
        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;
        const pageDetections = this.filteredDetections.slice(start, end);
        
        pageDetections.forEach(d => {
            this.selectedRows.add(d.id);
        });
        
        this.render();
        this.updateSelectionCount();
    }
    
    /**
     * Clear all selections
     */
    clearSelection() {
        this.selectedRows.clear();
        this.render();
        this.updateSelectionCount();
    }
    
    // ========================================================================
    // Pagination
    // ========================================================================
    
    /**
     * Update pagination controls
     */
    updatePagination() {
        if (!this.paginationContainer) return;
        
        const totalPages = Math.ceil(this.filteredDetections.length / this.pageSize);
        const start = (this.currentPage - 1) * this.pageSize + 1;
        const end = Math.min(start + this.pageSize - 1, this.filteredDetections.length);
        
        this.paginationContainer.innerHTML = `
            <div class="pagination-info">
                Showing ${start} to ${end} of ${this.filteredDetections.length} entries
            </div>
            <div class="pagination">
                <button class="pagination-btn" ${this.currentPage === 1 ? 'disabled' : ''} data-page="prev">
                    <i class="fas fa-chevron-left"></i> Previous
                </button>
                ${this.generatePageButtons(totalPages)}
                <button class="pagination-btn" ${this.currentPage === totalPages || totalPages === 0 ? 'disabled' : ''} data-page="next">
                    Next <i class="fas fa-chevron-right"></i>
                </button>
            </div>
            <div class="items-per-page">
                <select id="pageSizeSelect">
                    <option value="10" ${this.pageSize === 10 ? 'selected' : ''}>10</option>
                    <option value="20" ${this.pageSize === 20 ? 'selected' : ''}>20</option>
                    <option value="50" ${this.pageSize === 50 ? 'selected' : ''}>50</option>
                    <option value="100" ${this.pageSize === 100 ? 'selected' : ''}>100</option>
                </select>
                <span>per page</span>
            </div>
        `;
        
        // Attach pagination event listeners
        const prevBtn = this.paginationContainer.querySelector('[data-page="prev"]');
        const nextBtn = this.paginationContainer.querySelector('[data-page="next"]');
        const pageBtns = this.paginationContainer.querySelectorAll('.pagination-btn[data-page]');
        const pageSizeSelect = this.paginationContainer.querySelector('#pageSizeSelect');
        
        if (prevBtn && !prevBtn.disabled) {
            prevBtn.addEventListener('click', () => this.goToPage(this.currentPage - 1));
        }
        if (nextBtn && !nextBtn.disabled) {
            nextBtn.addEventListener('click', () => this.goToPage(this.currentPage + 1));
        }
        pageBtns.forEach(btn => {
            if (btn.dataset.page && btn.dataset.page !== 'prev' && btn.dataset.page !== 'next') {
                btn.addEventListener('click', () => this.goToPage(parseInt(btn.dataset.page)));
            }
        });
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', (e) => {
                this.pageSize = parseInt(e.target.value);
                this.currentPage = 1;
                this.render();
                this.updatePagination();
            });
        }
    }
    
    /**
     * Generate page buttons HTML
     * @param {number} totalPages - Total number of pages
     * @returns {string} HTML string
     */
    generatePageButtons(totalPages) {
        let buttons = '';
        const maxVisible = 5;
        let startPage = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        let endPage = Math.min(totalPages, startPage + maxVisible - 1);
        
        if (endPage - startPage + 1 < maxVisible) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }
        
        for (let i = startPage; i <= endPage; i++) {
            buttons += `<button class="pagination-btn ${i === this.currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
        }
        
        return buttons;
    }
    
    /**
     * Go to specific page
     * @param {number} page - Page number
     */
    goToPage(page) {
        const totalPages = Math.ceil(this.filteredDetections.length / this.pageSize);
        if (page < 1 || page > totalPages) return;
        
        this.currentPage = page;
        this.render();
        this.updatePagination();
        
        // Scroll to top of table
        this.container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // ========================================================================
    // Export Functions
    // ========================================================================
    
    /**
     * Export current data
     */
    async exportData() {
        const format = await this.showExportDialog();
        if (!format) return;
        
        try {
            const response = await fetch(`/api/export/detections?format=${format}&${this.getFilterParams()}`);
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `detections_${new Date().toISOString()}.${format}`;
            a.click();
            URL.revokeObjectURL(url);
            this.showToast(`Exported as ${format.toUpperCase()}`, 'success');
        } catch (error) {
            console.error('Export failed:', error);
            this.showToast('Export failed', 'error');
        }
    }
    
    /**
     * Export selected detections
     */
    async exportSelected() {
        const ids = Array.from(this.selectedRows);
        if (ids.length === 0) return;
        
        try {
            const response = await fetch('/api/export/detections', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids, format: 'json' })
            });
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `selected_detections_${new Date().toISOString()}.json`;
            a.click();
            URL.revokeObjectURL(url);
            this.showToast(`Exported ${ids.length} detections`, 'success');
        } catch (error) {
            console.error('Export failed:', error);
            this.showToast('Export failed', 'error');
        }
    }
    
    /**
     * Delete selected detections
     */
    async deleteSelected() {
        const ids = Array.from(this.selectedRows);
        if (ids.length === 0) return;
        
        const confirmed = confirm(`Are you sure you want to delete ${ids.length} detection(s)? This action cannot be undone.`);
        if (!confirmed) return;
        
        try {
            const response = await fetch('/api/detections', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids })
            });
            const data = await response.json();
            if (data.success) {
                this.detections = this.detections.filter(d => !ids.includes(d.id));
                this.selectedRows.clear();
                this.applyFilters();
                this.showToast(`Deleted ${ids.length} detection(s)`, 'success');
            }
        } catch (error) {
            console.error('Delete failed:', error);
            this.showToast('Delete failed', 'error');
        }
    }
    
    // ========================================================================
    // Utility Functions
    // ========================================================================
    
    /**
     * Format timestamp
     * @param {string} timestamp - ISO timestamp
     * @returns {string} Formatted timestamp
     */
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return `
            <div class="detection-timestamp">
                <span class="time">${date.toLocaleTimeString()}</span>
                <span class="date">${date.toLocaleDateString()}</span>
            </div>
        `;
    }
    
    /**
     * Format confidence
     * @param {number} confidence - Confidence value
     * @returns {string} HTML string
     */
    formatConfidence(confidence) {
        const percent = Math.round((confidence || 0) * 100);
        const confidenceClass = percent >= 80 ? 'high' : (percent >= 60 ? 'medium' : 'low');
        return `
            <div class="detection-confidence">
                <div class="confidence-value ${confidenceClass}">${percent}%</div>
                <div class="confidence-bar">
                    <div class="confidence-bar-fill ${confidenceClass}" style="width: ${percent}%"></div>
                </div>
            </div>
        `;
    }
    
    /**
     * Format threat level
     * @param {string} threat - Threat level
     * @returns {string} HTML string
     */
    formatThreat(threat) {
        const level = (threat || 'UNKNOWN').toLowerCase();
        return `<span class="badge badge-threat-${level}">${threat || 'UNKNOWN'}</span>`;
    }
    
    /**
     * Format frequency
     * @param {number} freq - Frequency in Hz
     * @returns {string} Formatted frequency
     */
    formatFrequency(freq) {
        if (!freq) return '-';
        if (freq >= 1e9) return `${(freq / 1e9).toFixed(3)} GHz`;
        if (freq >= 1e6) return `${(freq / 1e6).toFixed(2)} MHz`;
        return `${(freq / 1e3).toFixed(2)} kHz`;
    }
    
    /**
     * Format signal strength
     * @param {number} signal - Signal strength in dBm
     * @returns {string} HTML string
     */
    formatSignal(signal) {
        if (!signal) return '-';
        const strengthClass = signal >= -50 ? 'strong' : (signal >= -70 ? 'medium' : 'weak');
        const bars = signal >= -40 ? 5 : (signal >= -50 ? 4 : (signal >= -60 ? 3 : (signal >= -70 ? 2 : 1)));
        
        let barsHtml = '';
        for (let i = 1; i <= 5; i++) {
            barsHtml += `<div class="signal-bar signal-bar-${i} ${i <= bars ? 'active' : ''}"></div>`;
        }
        
        return `
            <div class="detection-signal">
                <div class="signal-value ${strengthClass}">${signal.toFixed(0)} dBm</div>
                <div class="signal-bars">${barsHtml}</div>
            </div>
        `;
    }
    
    /**
     * Format location
     * @param {Object} row - Detection row data
     * @returns {string} HTML string
     */
    formatLocation(row) {
        if (!row.latitude || !row.longitude) return '-';
        return `
            <div class="detection-location">
                <div class="location-coords">
                    ${row.latitude.toFixed(4)}, ${row.longitude.toFixed(4)}
                </div>
                ${row.location_name ? `<div class="location-name">${row.location_name}</div>` : ''}
            </div>
        `;
    }
    
    /**
     * Get threat class for row styling
     * @param {string} threat - Threat level
     * @returns {string} CSS class
     */
    getThreatClass(threat) {
        const level = (threat || '').toLowerCase();
        const classes = {
            'critical': 'table-row-critical',
            'high': 'table-row-high',
            'medium': 'table-row-medium',
            'low': 'table-row-low'
        };
        return classes[level] || '';
    }
    
    /**
     * Update drone type filter options
     */
    updateDroneTypeFilter() {
        const types = new Set();
        this.detections.forEach(d => {
            if (d.drone_type) types.add(d.drone_type);
        });
        
        const sortedTypes = Array.from(types).sort();
        if (this.droneTypeFilter) {
            this.droneTypeFilter.innerHTML = '<option value="">All Types</option>' +
                sortedTypes.map(type => `<option value="${type}">${type}</option>`).join('');
        }
    }
    
    /**
     * Get filter parameters as query string
     * @returns {string} Query string
     */
    getFilterParams() {
        const params = new URLSearchParams();
        if (this.filters.search) params.append('search', this.filters.search);
        if (this.filters.threatLevel) params.append('threat_level', this.filters.threatLevel);
        if (this.filters.droneType) params.append('drone_type', this.filters.droneType);
        if (this.filters.startDate) params.append('start_date', this.filters.startDate.toISOString());
        if (this.filters.endDate) params.append('end_date', this.filters.endDate.toISOString());
        if (this.filters.minConfidence) params.append('min_confidence', this.filters.minConfidence);
        return params.toString();
    }
    
    /**
     * Show export format dialog
     * @returns {Promise<string|null>} Selected format
     */
    showExportDialog() {
        return new Promise((resolve) => {
            const formats = ['csv', 'json', 'excel'];
            // Simple prompt for demo - in production use a modal
            const format = prompt('Export format? (csv, json, excel)', 'csv');
            resolve(formats.includes(format) ? format : null);
        });
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
            alert(message);
        }
    }
    
    /**
     * View detection details
     * @param {string} id - Detection ID
     */
    viewDetails(id) {
        const detection = this.detections.find(d => d.id === id);
        if (detection) {
            // Open modal with detection details
            this.showDetectionModal(detection);
        }
    }
    
    /**
     * Analyze detection
     * @param {string} id - Detection ID
     */
    analyze(id) {
        const detection = this.detections.find(d => d.id === id);
        if (detection) {
            // Open spectrum analysis view
            if (typeof window.analyzeSpectrum === 'function') {
                window.analyzeSpectrum(detection);
            }
        }
    }
    
    /**
     * Show detection modal
     * @param {Object} detection - Detection data
     */
    showDetectionModal(detection) {
        // Implementation for modal display
        console.log('Show detection modal:', detection);
    }
    
    /**
     * Destroy the table view
     */
    destroy() {
        if (this.ws) {
            this.ws.unsubscribe('detection');
            this.ws.unsubscribe('detection_update');
        }
        if (this.bulkActionsBar) {
            this.bulkActionsBar.remove();
        }
        this.container.innerHTML = '';
    }
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Debounce function for search input
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
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

// For ES modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DetectionTableView;
}

// For browser global
if (typeof window !== 'undefined') {
    window.DetectionTableView = DetectionTableView;
}

// ============================================================================
// Example Usage
// ============================================================================

/**
 * Example of how to use the detection table view
 */
function exampleUsage() {
    // Create container
    const container = document.getElementById('detections-container');
    
    // Create table view
    const table = new DetectionTableView({
        container: container,
        pageSize: 25,
        showPagination: true,
        onRowClick: (detection) => {
            console.log('Row clicked:', detection);
            // Open detail view
        },
        onSelectionChange: (selectedIds) => {
            console.log('Selected IDs:', selectedIds);
        }
    });
    
    // Access table methods
    window.detectionView = table;
}