/**
 * Main Application Logic
 * Handles UI updates, server management, and user interactions
 */

const app = {
    refreshInterval: null,
    refreshRate: 5000, // 5 seconds

    /**
     * Initialize application
     */
    init() {
        console.log('Dockercraft initializing...');
        
        // Load servers immediately
        this.loadServers();
        
        // Setup auto-refresh
        this.startAutoRefresh();
        
        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();
        
        // Check API health
        this.checkHealth();
    },

    /**
     * Start auto-refresh timer
     */
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            // Only refresh if console is not open
            if (!consoleManager.isConnected()) {
                this.loadServers(true); // Silent refresh
            }
        }, this.refreshRate);
    },

    /**
     * Stop auto-refresh timer
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    },

    /**
     * Setup keyboard shortcuts
     */
    setupKeyboardShortcuts() {
        // Enter key in command input
        document.getElementById('command-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendCommand();
            }
        });

        // Escape key to close console
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && consoleManager.isConnected()) {
                this.closeConsole();
            }
        });
    },

    /**
     * Check API health
     */
    async checkHealth() {
        try {
            await API.checkHealth();
            console.log('API is healthy');
        } catch (error) {
            this.showError('Cannot connect to API. Is the backend running?');
        }
    },

    /**
     * Load all servers
     */
    async loadServers(silent = false) {
        try {
            const servers = await API.getServers();
            
            if (!silent) {
                document.getElementById('loading').classList.add('hidden');
                document.getElementById('servers').classList.remove('hidden');
            }
            
            this.renderServers(servers);
        } catch (error) {
            console.error('Failed to load servers:', error);
            if (!silent) {
                this.showError(`Failed to load servers: ${error.message}`);
            }
        }
    },

    /**
     * Render server cards
     */
    renderServers(servers) {
        const container = document.getElementById('servers');
        
        if (servers.length === 0) {
            container.innerHTML = '<div class="loading">No servers configured</div>';
            return;
        }

        container.innerHTML = servers.map(server => this.createServerCard(server)).join('');
    },

    /**
     * Create HTML for a server card
     */
    createServerCard(server) {
        const isRunning = server.status === 'running';
        const isStopped = server.status === 'stopped';
        
        return `
            <div class="server-card">
                <div class="server-header">
                    <div class="server-title">
                        <h2>${this.escapeHtml(server.name)}</h2>
                        <span class="server-id">${this.escapeHtml(server.id)}</span>
                    </div>
                    <span class="status-badge status-${server.status}">
                        ${server.status}
                    </span>
                        <button class="delete-server-btn"
                                onclick="app.deleteServer('${server.id}')">
                            ✖
                        </button>
                </div>
                
                <div class="server-info">
                    <div class="info-row">
                        <span class="info-label">Type:</span>
                        <span class="info-value">${this.escapeHtml(server.type)} ${this.escapeHtml(server.version)}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Players:</span>
                        <span class="info-value">${server.players_online}/${server.players_max}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Port:</span>
                        <span class="info-value">${server.port}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Memory:</span>
                        <span class="info-value">${server.memory_min} - ${server.memory_max}</span>
                    </div>
                </div>
                
                <div class="server-actions">
                    <button class="btn-start" 
                            onclick="app.startServer('${server.id}')"
                            ${isStopped ? '' : 'disabled'}>
                        Start
                    </button>
                    <button class="btn-stop"
                            onclick="app.stopServer('${server.id}')"
                            ${isRunning ? '' : 'disabled'}>
                        Stop
                    </button>
                    <button class="btn-restart"
                            onclick="app.restartServer('${server.id}')"
                            ${isRunning ? '' : 'disabled'}>
                        Restart
                    </button>
                    <button class="btn-console"
                            onclick="app.openConsole('${server.id}', '${this.escapeHtml(server.name)}')"
                            ${isRunning ? '' : 'disabled'}>
                        Console
                    </button>
                </div>
            </div>
        `;
    },

    /**
     * Start server
     */
    async startServer(serverId) {
        try {
            await API.startServer(serverId);
            this.showSuccess(`Starting server ${serverId}...`);
            
            // Refresh after a delay
            setTimeout(() => this.loadServers(true), 1000);
        } catch (error) {
            this.showError(`Failed to start server: ${error.message}`);
        }
    },

    /**
     * Stop server
     */
    async stopServer(serverId) {
        try {
            await API.stopServer(serverId);
            this.showSuccess(`Stopping server ${serverId}...`);
            
            // Close console if open for this server
            if (consoleManager.serverId === serverId) {
                this.closeConsole();
            }
            
            // Refresh after a delay
            setTimeout(() => this.loadServers(true), 1000);
        } catch (error) {
            this.showError(`Failed to stop server: ${error.message}`);
        }
    },

    /**
     * Restart server
     */
    async restartServer(serverId) {
        try {
            await API.restartServer(serverId);
            this.showSuccess(`Restarting server ${serverId}...`);
            
            // Close console if open for this server
            if (consoleManager.serverId === serverId) {
                this.closeConsole();
            }
            
            // Refresh after a delay
            setTimeout(() => this.loadServers(true), 2000);
        } catch (error) {
            this.showError(`Failed to restart server: ${error.message}`);
        }
    },

    /**
     * Delete server
     */
    async deleteServer(serverId) {
        try {
            await API.deleteServer(serverId);
            this.showSuccess(`Deleting server ${serverId}...`);
            
            // Close console if open for this server
            if (consoleManager.serverId === serverId) {
                this.closeConsole();
            }
            
            // Refresh after a delay
            setTimeout(() => this.loadServers(true), 1000);
        } catch (error) {
            this.showError(`Failed to delete server: ${error.message}`);
        }
    },

    /**
     * Open console for server
     */
    openConsole(serverId, serverName) {
        // Stop auto-refresh while console is open
        this.stopAutoRefresh();
        
        // Connect to console
        consoleManager.connect(serverId, serverName);
    },

    /**
     * Close console
     */
    closeConsole() {
        consoleManager.close();
        
        // Resume auto-refresh
        this.startAutoRefresh();
    },

    /**
     * Send command to server
     */
    sendCommand() {
        const input = document.getElementById('command-input');
        const command = input.value.trim();
        
        if (!command) {
            return;
        }

        // Send via WebSocket
        if (consoleManager.sendCommand(command)) {
            input.value = '';
        }
    },

    /**
     * Open modal for creating a new server
     */
    openModal() {
        const modal = document.getElementById('create-server-modal');
        modal.classList.remove('hidden');
    },

    /**
     * Close modal for creating a new server
     */
    closeModal() {
        const modal = document.getElementById('create-server-modal');
        modal.classList.add('hidden');
    },

    /**
     * Submit the modal form for creating a new server
     */
    async submitModal() {
        const serverData = {
            id: document.getElementById('server-id').value.trim(),
            name: document.getElementById('server-name').value.trim(),
            type: document.getElementById('server-type').value,
            version: document.getElementById('server-version').value.trim(),
            memory_min: document.getElementById('memory-min').value.trim(),
            memory_max: document.getElementById('memory-max').value.trim(),
            port: parseInt(document.getElementById('server-port').value, 10),
            rcon_port: parseInt(document.getElementById('rcon-port').value, 10)
        };

        try {
            await API.createServer(serverData);
            app.showSuccess(`Server "${serverData.name}" created!`);
            app.loadServers(true);
            this.closeModal();
            form.reset();
        } catch (error) {
            app.showError(`Failed to create server: ${error.message}`);
        }
    },

    /**
     * Show error message
     */
    showError(message) {
        const errorEl = document.getElementById('error-message');
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorEl.classList.add('hidden');
        }, 5000);
    },

    /**
     * Show success message
     */
    showSuccess(message) {
        const successEl = document.getElementById('success-message');
        successEl.textContent = message;
        successEl.classList.remove('hidden');
        
        // Auto-hide after 3 seconds
        setTimeout(() => {
            successEl.classList.add('hidden');
        }, 3000);
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, (m) => map[m]);
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    app.init();
});

// Handle 'open' create server button clicks
const openBtn = document.getElementById('open-create-server');
openBtn.addEventListener('click', () => {
    app.openModal();
});

// Handle 'close' create server button clicks
const closeBtn = document.getElementById('close-create-server');
closeBtn.addEventListener('click', () => {
    app.closeModal();
});

// Handle 'submit' create server button clicks
const form = document.getElementById('create-server-form');
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    app.submitModal();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    app.stopAutoRefresh();
    if (consoleManager.isConnected()) {
        consoleManager.close();
    }
});

// Make app available globally for onclick handlers
window.app = app;
