/**
 * Drone Detection System - WebSocket Manager
 * Version: 2.0.0
 * 
 * This module handles WebSocket connections for real-time data streaming,
 * including automatic reconnection, message queuing, subscription management,
 * and heartbeat monitoring.
 */

// ============================================================================
// WebSocket Manager Class
// ============================================================================

class WebSocketManager {
    /**
     * Create a new WebSocket manager
     * @param {Object} options - Configuration options
     * @param {string} options.url - WebSocket server URL
     * @param {number} options.reconnectDelay - Initial reconnect delay (ms)
     * @param {number} options.maxReconnectAttempts - Maximum reconnection attempts
     * @param {number} options.heartbeatInterval - Heartbeat interval (ms)
     * @param {boolean} options.debug - Enable debug logging
     */
    constructor(options = {}) {
        this.url = options.url || 'ws://localhost:8082/ws';
        this.reconnectDelay = options.reconnectDelay || 3000;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.heartbeatInterval = options.heartbeatInterval || 30000;
        this.debug = options.debug || false;
        
        // Connection state
        this.ws = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.messageQueue = [];
        this.subscriptions = new Set();
        
        // Event callbacks
        this.callbacks = {
            onOpen: [],
            onClose: [],
            onError: [],
            onMessage: [],
            onReconnect: [],
            onMaxReconnect: []
        };
        
        // Message handlers by type
        this.messageHandlers = new Map();
        
        // Pending promises for request/response
        this.pendingRequests = new Map();
        this.requestId = 0;
        
        this.log('WebSocket Manager initialized');
    }
    
    // ========================================================================
    // Connection Management
    // ========================================================================
    
    /**
     * Connect to WebSocket server
     * @returns {Promise} Promise that resolves when connected
     */
    connect() {
        return new Promise((resolve, reject) => {
            if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || 
                this.ws.readyState === WebSocket.OPEN)) {
                this.log('Already connecting or connected');
                resolve();
                return;
            }
            
            this.log(`Connecting to ${this.url}...`);
            
            try {
                this.ws = new WebSocket(this.url);
                
                const timeout = setTimeout(() => {
                    reject(new Error('Connection timeout'));
                }, 10000);
                
                this.ws.onopen = (event) => {
                    clearTimeout(timeout);
                    this.handleOpen(event);
                    resolve();
                };
                
                this.ws.onclose = (event) => {
                    clearTimeout(timeout);
                    this.handleClose(event);
                    reject(new Error('Connection closed'));
                };
                
                this.ws.onerror = (event) => {
                    clearTimeout(timeout);
                    this.handleError(event);
                    reject(new Error('Connection error'));
                };
                
                this.ws.onmessage = (event) => {
                    this.handleMessage(event);
                };
                
            } catch (error) {
                this.log(`Connection error: ${error}`, 'error');
                reject(error);
            }
        });
    }
    
    /**
     * Disconnect from WebSocket server
     */
    disconnect() {
        this.log('Disconnecting...');
        
        // Clear timers
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
        
        // Close connection
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.close(1000, 'Normal closure');
        }
        
        this.connected = false;
        this.ws = null;
    }
    
    /**
     * Handle WebSocket open event
     * @param {Event} event - WebSocket event
     */
    handleOpen(event) {
        this.log('Connected to WebSocket server');
        this.connected = true;
        this.reconnectAttempts = 0;
        
        // Start heartbeat
        this.startHeartbeat();
        
        // Resubscribe to channels
        this.resubscribe();
        
        // Send queued messages
        this.flushMessageQueue();
        
        // Trigger callbacks
        this.triggerCallbacks('onOpen', event);
    }
    
    /**
     * Handle WebSocket close event
     * @param {CloseEvent} event - WebSocket close event
     */
    handleClose(event) {
        this.log(`Connection closed: ${event.code} - ${event.reason}`);
        this.connected = false;
        
        // Stop heartbeat
        this.stopHeartbeat();
        
        // Trigger callbacks
        this.triggerCallbacks('onClose', event);
        
        // Attempt reconnection
        this.scheduleReconnect();
    }
    
    /**
     * Handle WebSocket error event
     * @param {Event} event - WebSocket error event
     */
    handleError(event) {
        this.log(`Connection error: ${event}`, 'error');
        this.triggerCallbacks('onError', event);
    }
    
    /**
     * Handle WebSocket message event
     * @param {MessageEvent} event - WebSocket message event
     */
    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.log(`Received: ${data.type}`, 'debug');
            
            // Handle request/response
            if (data.id && this.pendingRequests.has(data.id)) {
                const { resolve, reject } = this.pendingRequests.get(data.id);
                this.pendingRequests.delete(data.id);
                
                if (data.error) {
                    reject(new Error(data.error));
                } else {
                    resolve(data);
                }
                return;
            }
            
            // Handle message by type
            if (this.messageHandlers.has(data.type)) {
                const handlers = this.messageHandlers.get(data.type);
                handlers.forEach(handler => {
                    try {
                        handler(data.data, data);
                    } catch (error) {
                        this.log(`Handler error for ${data.type}: ${error}`, 'error');
                    }
                });
            }
            
            // Trigger generic message callbacks
            this.triggerCallbacks('onMessage', data);
            
        } catch (error) {
            this.log(`Failed to parse message: ${error}`, 'error');
        }
    }
    
    // ========================================================================
    // Reconnection Logic
    // ========================================================================
    
    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.log('Max reconnection attempts reached', 'error');
            this.triggerCallbacks('onMaxReconnect');
            return;
        }
        
        const delay = this.calculateReconnectDelay();
        this.log(`Scheduling reconnect attempt ${this.reconnectAttempts + 1} in ${delay}ms`);
        
        this.reconnectTimer = setTimeout(() => {
            this.reconnect();
        }, delay);
    }
    
    /**
     * Calculate reconnect delay with exponential backoff
     * @returns {number} Delay in milliseconds
     */
    calculateReconnectDelay() {
        const delay = Math.min(
            this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts),
            30000 // Max 30 seconds
        );
        return delay;
    }
    
    /**
     * Attempt to reconnect
     */
    async reconnect() {
        this.reconnectAttempts++;
        this.log(`Reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
        
        try {
            await this.connect();
            this.triggerCallbacks('onReconnect', { attempts: this.reconnectAttempts });
        } catch (error) {
            this.log(`Reconnect failed: ${error}`, 'error');
            this.scheduleReconnect();
        }
    }
    
    // ========================================================================
    // Heartbeat Management
    // ========================================================================
    
    /**
     * Start heartbeat interval
     */
    startHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
        }
        
        this.heartbeatTimer = setInterval(() => {
            this.sendHeartbeat();
        }, this.heartbeatInterval);
    }
    
    /**
     * Stop heartbeat interval
     */
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }
    
    /**
     * Send heartbeat ping
     */
    sendHeartbeat() {
        if (this.isConnected()) {
            this.send('ping', { timestamp: Date.now() });
        }
    }
    
    // ========================================================================
    // Message Sending
    // ========================================================================
    
    /**
     * Send a message through the WebSocket
     * @param {string} type - Message type
     * @param {Object} data - Message data
     * @returns {boolean} True if sent or queued
     */
    send(type, data = {}) {
        const message = { type, data, timestamp: Date.now() };
        
        if (this.isConnected()) {
            try {
                this.ws.send(JSON.stringify(message));
                this.log(`Sent: ${type}`, 'debug');
                return true;
            } catch (error) {
                this.log(`Failed to send: ${error}`, 'error');
                this.queueMessage(message);
                return false;
            }
        } else {
            this.queueMessage(message);
            return false;
        }
    }
    
    /**
     * Send a request and wait for response
     * @param {string} type - Request type
     * @param {Object} data - Request data
     * @param {number} timeout - Timeout in milliseconds
     * @returns {Promise} Promise that resolves with response
     */
    sendRequest(type, data = {}, timeout = 30000) {
        return new Promise((resolve, reject) => {
            const id = ++this.requestId;
            const message = { type, data, id, timestamp: Date.now() };
            
            // Set timeout
            const timeoutId = setTimeout(() => {
                if (this.pendingRequests.has(id)) {
                    this.pendingRequests.delete(id);
                    reject(new Error(`Request timeout: ${type}`));
                }
            }, timeout);
            
            // Store promise callbacks
            this.pendingRequests.set(id, {
                resolve: (result) => {
                    clearTimeout(timeoutId);
                    resolve(result);
                },
                reject: (error) => {
                    clearTimeout(timeoutId);
                    reject(error);
                }
            });
            
            // Send message
            if (this.isConnected()) {
                try {
                    this.ws.send(JSON.stringify(message));
                    this.log(`Sent request: ${type} (${id})`, 'debug');
                } catch (error) {
                    this.pendingRequests.delete(id);
                    reject(error);
                }
            } else {
                this.pendingRequests.delete(id);
                reject(new Error('Not connected'));
            }
        });
    }
    
    /**
     * Queue message for later sending
     * @param {Object} message - Message to queue
     */
    queueMessage(message) {
        if (this.messageQueue.length < 1000) {
            this.messageQueue.push(message);
            this.log(`Message queued (${this.messageQueue.length} total)`, 'debug');
        } else {
            this.log('Message queue full, dropping message', 'warn');
        }
    }
    
    /**
     * Flush queued messages
     */
    flushMessageQueue() {
        if (!this.isConnected()) return;
        
        const messages = [...this.messageQueue];
        this.messageQueue = [];
        
        messages.forEach(message => {
            try {
                this.ws.send(JSON.stringify(message));
                this.log(`Sent queued: ${message.type}`, 'debug');
            } catch (error) {
                this.log(`Failed to send queued message: ${error}`, 'error');
                this.queueMessage(message);
            }
        });
    }
    
    // ========================================================================
    // Subscription Management
    // ========================================================================
    
    /**
     * Subscribe to a message type
     * @param {string} type - Message type to subscribe to
     * @param {Function} handler - Message handler function
     */
    subscribe(type, handler) {
        if (!this.messageHandlers.has(type)) {
            this.messageHandlers.set(type, []);
        }
        this.messageHandlers.get(type).push(handler);
        
        // Send subscription message if connected
        if (this.isConnected()) {
            this.send('subscribe', { channel: type });
        }
        
        this.subscriptions.add(type);
        this.log(`Subscribed to: ${type}`);
    }
    
    /**
     * Unsubscribe from a message type
     * @param {string} type - Message type to unsubscribe from
     * @param {Function} handler - Specific handler to remove (optional)
     */
    unsubscribe(type, handler = null) {
        if (this.messageHandlers.has(type)) {
            if (handler) {
                const handlers = this.messageHandlers.get(type);
                const index = handlers.indexOf(handler);
                if (index !== -1) {
                    handlers.splice(index, 1);
                }
                if (handlers.length === 0) {
                    this.messageHandlers.delete(type);
                    this.subscriptions.delete(type);
                    
                    if (this.isConnected()) {
                        this.send('unsubscribe', { channel: type });
                    }
                }
            } else {
                this.messageHandlers.delete(type);
                this.subscriptions.delete(type);
                
                if (this.isConnected()) {
                    this.send('unsubscribe', { channel: type });
                }
            }
        }
        
        this.log(`Unsubscribed from: ${type}`);
    }
    
    /**
     * Resubscribe to all channels after reconnection
     */
    resubscribe() {
        this.subscriptions.forEach(type => {
            this.send('subscribe', { channel: type });
            this.log(`Resubscribed to: ${type}`, 'debug');
        });
    }
    
    // ========================================================================
    // Event Callbacks
    // ========================================================================
    
    /**
     * Register event callback
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    on(event, callback) {
        if (this.callbacks[event]) {
            this.callbacks[event].push(callback);
        }
    }
    
    /**
     * Trigger event callbacks
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    triggerCallbacks(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    this.log(`Callback error for ${event}: ${error}`, 'error');
                }
            });
        }
    }
    
    // ========================================================================
    // Utility Methods
    // ========================================================================
    
    /**
     * Check if connected
     * @returns {boolean} True if connected
     */
    isConnected() {
        return this.connected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }
    
    /**
     * Get connection state
     * @returns {Object} Connection state information
     */
    getConnectionState() {
        const states = {
            [WebSocket.CONNECTING]: 'connecting',
            [WebSocket.OPEN]: 'open',
            [WebSocket.CLOSING]: 'closing',
            [WebSocket.CLOSED]: 'closed'
        };
        
        return {
            connected: this.isConnected(),
            readyState: this.ws ? states[this.ws.readyState] : 'none',
            reconnectAttempts: this.reconnectAttempts,
            messageQueueSize: this.messageQueue.length,
            subscriptions: Array.from(this.subscriptions)
        };
    }
    
    /**
     * Get connection statistics
     * @returns {Object} Connection statistics
     */
    getStats() {
        return {
            connected: this.isConnected(),
            reconnectAttempts: this.reconnectAttempts,
            messageQueueSize: this.messageQueue.length,
            subscriptions: this.subscriptions.size,
            pendingRequests: this.pendingRequests.size
        };
    }
    
    /**
     * Clear all subscriptions and handlers
     */
    clear() {
        this.messageHandlers.clear();
        this.subscriptions.clear();
        this.pendingRequests.clear();
        this.messageQueue = [];
        
        // Clear callbacks except connection events
        for (const event in this.callbacks) {
            if (event !== 'onMessage') {
                this.callbacks[event] = [];
            }
        }
    }
    
    /**
     * Log message if debug is enabled
     * @param {string} message - Log message
     * @param {string} level - Log level
     */
    log(message, level = 'info') {
        if (!this.debug && level === 'debug') return;
        
        const prefix = '[WebSocketManager]';
        switch(level) {
            case 'error':
                console.error(prefix, message);
                break;
            case 'warn':
                console.warn(prefix, message);
                break;
            case 'debug':
                console.debug(prefix, message);
                break;
            default:
                console.log(prefix, message);
        }
    }
}

// ============================================================================
// Default Instance with Common Subscriptions
// ============================================================================

let defaultInstance = null;

/**
 * Get or create default WebSocket manager instance
 * @param {Object} options - Configuration options
 * @returns {WebSocketManager} WebSocket manager instance
 */
function getWebSocketManager(options = {}) {
    if (!defaultInstance) {
        defaultInstance = new WebSocketManager(options);
        
        // Auto-connect when created
        defaultInstance.connect().catch(error => {
            console.error('Failed to connect WebSocket:', error);
        });
    }
    return defaultInstance;
}

/**
 * Reset default WebSocket manager instance
 */
function resetWebSocketManager() {
    if (defaultInstance) {
        defaultInstance.disconnect();
        defaultInstance = null;
    }
}

// ============================================================================
// Convenience Functions
// ============================================================================

/**
 * Send a message through the default WebSocket connection
 * @param {string} type - Message type
 * @param {Object} data - Message data
 * @returns {boolean} True if sent or queued
 */
function sendWSMessage(type, data = {}) {
    const ws = getWebSocketManager();
    return ws.send(type, data);
}

/**
 * Subscribe to a message type
 * @param {string} type - Message type
 * @param {Function} handler - Message handler
 */
function subscribeToWS(type, handler) {
    const ws = getWebSocketManager();
    ws.subscribe(type, handler);
}

/**
 * Unsubscribe from a message type
 * @param {string} type - Message type
 * @param {Function} handler - Specific handler to remove
 */
function unsubscribeFromWS(type, handler = null) {
    const ws = getWebSocketManager();
    ws.unsubscribe(type, handler);
}

/**
 * Check if WebSocket is connected
 * @returns {boolean} True if connected
 */
function isWSConnected() {
    const ws = getWebSocketManager();
    return ws.isConnected();
}

// ============================================================================
// Export for module systems
// ============================================================================

// For ES modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        WebSocketManager,
        getWebSocketManager,
        resetWebSocketManager,
        sendWSMessage,
        subscribeToWS,
        unsubscribeFromWS,
        isWSConnected
    };
}

// For browser global
if (typeof window !== 'undefined') {
    window.WebSocketManager = WebSocketManager;
    window.getWebSocketManager = getWebSocketManager;
    window.sendWSMessage = sendWSMessage;
    window.subscribeToWS = subscribeToWS;
    window.unsubscribeFromWS = unsubscribeFromWS;
    window.isWSConnected = isWSConnected;
}

// ============================================================================
// Example Usage
// ============================================================================

/**
 * Example of how to use the WebSocket manager
 */
function exampleUsage() {
    // Get or create WebSocket manager
    const ws = getWebSocketManager({
        url: 'ws://localhost:8082/ws',
        debug: true,
        maxReconnectAttempts: 5
    });
    
    // Register callbacks
    ws.on('onOpen', () => {
        console.log('Connected to WebSocket server');
    });
    
    ws.on('onClose', () => {
        console.log('Disconnected from WebSocket server');
    });
    
    ws.on('onReconnect', (data) => {
        console.log(`Reconnected after ${data.attempts} attempts`);
    });
    
    // Subscribe to message types
    ws.subscribe('detection', (data) => {
        console.log('New detection:', data);
        updateUI('detection', data);
    });
    
    ws.subscribe('alert', (data) => {
        console.log('New alert:', data);
        showAlertNotification(data);
    });
    
    ws.subscribe('metrics', (data) => {
        console.log('System metrics:', data);
        updateMetrics(data);
    });
    
    // Send messages
    ws.send('get_status', {});
    ws.send('subscribe', { channel: 'positions' });
    
    // Send request with response
    ws.sendRequest('get_detections', { limit: 100 })
        .then(response => {
            console.log('Detections:', response.data);
        })
        .catch(error => {
            console.error('Failed to get detections:', error);
        });
}

// Export for browser
if (typeof window !== 'undefined') {
    // Auto-initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        // Initialize default WebSocket manager
        getWebSocketManager();
    });
}