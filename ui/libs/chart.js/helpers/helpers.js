/**
 * Chart.js Helpers
 * 
 * Utility functions for Chart.js integration
 */

const ChartHelpers = {
    /**
     * Get chart colors based on theme
     * @param {string} theme - 'dark' or 'light'
     * @returns {Object} Color scheme
     */
    getThemeColors: function(theme = 'dark') {
        if (theme === 'light') {
            return {
                grid: 'rgba(0, 0, 0, 0.1)',
                text: '#333333',
                border: '#4facfe',
                background: 'rgba(79, 172, 254, 0.1)',
                threatHigh: '#f44336',
                threatMedium: '#ff9800',
                threatLow: '#4caf50'
            };
        }
        return {
            grid: 'rgba(255, 255, 255, 0.1)',
            text: '#e0e0e0',
            border: '#4facfe',
            background: 'rgba(79, 172, 254, 0.1)',
            threatHigh: '#f44336',
            threatMedium: '#ff9800',
            threatLow: '#4caf50'
        };
    },
    
    /**
     * Create gradient for chart
     * @param {CanvasRenderingContext2D} ctx - Canvas context
     * @param {string} color - Base color
     * @returns {CanvasGradient} Gradient
     */
    createGradient: function(ctx, color) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, color);
        gradient.addColorStop(1, 'rgba(79, 172, 254, 0)');
        return gradient;
    },
    
    /**
     * Format tooltip values
     * @param {Object} context - Tooltip context
     * @returns {string} Formatted label
     */
    formatTooltip: function(context) {
        let label = context.dataset.label || '';
        if (label) {
            label += ': ';
        }
        if (context.parsed.y !== null) {
            label += context.parsed.y.toLocaleString();
        }
        return label;
    },
    
    /**
     * Get chart configuration for dark/light mode
     * @param {string} theme - Theme name
     * @returns {Object} Chart options
     */
    getBaseOptions: function(theme) {
        const colors = this.getThemeColors(theme);
        return {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: {
                        color: colors.text,
                        usePointStyle: true,
                        boxWidth: 10
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleColor: colors.text,
                    bodyColor: colors.text,
                    borderColor: colors.border,
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    ticks: { color: colors.text },
                    grid: { color: colors.grid }
                },
                y: {
                    ticks: { color: colors.text },
                    grid: { color: colors.grid },
                    beginAtZero: true
                }
            }
        };
    }
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChartHelpers;
}
if (typeof window !== 'undefined') {
    window.ChartHelpers = ChartHelpers;
}