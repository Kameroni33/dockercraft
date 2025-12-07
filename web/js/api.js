/**
 * API Client
 * Handles all communication with the FastAPI backend
 */

const API = {
    baseUrl: '/api',

    /**
     * Generic fetch wrapper with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            // Handle 204 No Content
            if (response.status === 204) {
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error(`API request failed: ${endpoint}`, error);
            throw error;
        }
    },

    /**
     * GET request helper
     */
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    /**
     * POST request helper
     */
    async post(endpoint, data = null) {
        return this.request(endpoint, {
            method: 'POST',
            body: data ? JSON.stringify(data) : undefined,
        });
    },

    /**
     * DELETE request helper
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    },

    // =================================
    // Server Endpoints
    // =================================

    /**
     * Get all servers
     */
    async getServers() {
        return this.get('/servers');
    },

    /**
     * Get specific server
     */
    async getServer(serverId) {
        return this.get(`/servers/${serverId}`);
    },

    /**
     * Create new server
     */
    async createServer(serverData) {
        return this.post('/servers', serverData);
    },

    /**
     * Delete server
     */
    async deleteServer(serverId) {
        return this.delete(`/servers/${serverId}`);
    },

    /**
     * Start server
     */
    async startServer(serverId) {
        return this.post(`/servers/${serverId}/start`);
    },

    /**
     * Stop server
     */
    async stopServer(serverId) {
        return this.post(`/servers/${serverId}/stop`);
    },

    /**
     * Restart server
     */
    async restartServer(serverId) {
        return this.post(`/servers/${serverId}/restart`);
    },

    /**
     * Execute command on server
     */
    async executeCommand(serverId, command) {
        return this.post(`/servers/${serverId}/command`, { command });
    },

    /**
     * Get server logs
     */
    async getLogs(serverId, lines = 100) {
        return this.get(`/servers/${serverId}/logs?lines=${lines}`);
    },

    // =================================
    // Backup Endpoints
    // =================================

    /**
     * Get backups for server
     */
    async getBackups(serverId) {
        return this.get(`/backups/${serverId}`);
    },

    /**
     * Create backup
     */
    async createBackup(serverId, description = null) {
        return this.post('/backups', { server_id: serverId, description });
    },

    /**
     * Restore backup
     */
    async restoreBackup(backupId) {
        return this.post(`/backups/${backupId}/restore`);
    },

    /**
     * Delete backup
     */
    async deleteBackup(backupId) {
        return this.delete(`/backups/${backupId}`);
    },

    // =================================
    // Mod Endpoints
    // =================================

    /**
     * Search mods
     */
    async searchMods(query, limit = 10) {
        return this.get(`/mods/search?query=${encodeURIComponent(query)}&limit=${limit}`);
    },

    /**
     * Get mod versions
     */
    async getModVersions(modSlug) {
        return this.get(`/mods/${modSlug}/versions`);
    },

    /**
     * Install mod
     */
    async installMod(serverId, modSlug, version) {
        return this.post('/mods/install', {
            server_id: serverId,
            mod_slug: modSlug,
            version: version
        });
    },

    // =================================
    // Health Check
    // =================================

    /**
     * Check API health
     */
    async checkHealth() {
        return this.get('/health');
    }
};

// Make API available globally
window.API = API;
