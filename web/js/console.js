/**
 * Console Manager
 * Handles WebSocket connection for live console
 */

class ConsoleManager {
    constructor() {
        this.ws = null;
        this.serverId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000; // 2 seconds
    }

    /**
     * Connect to server console
     */
    connect(serverId, serverName) {
        this.serverId = serverId;
        
        // Show console section
        document.getElementById('console-server-name').textContent = serverName;
        document.getElementById('console-section').classList.remove('hidden');
        this.clearOutput();
        this.appendOutput('Connecting to console...\n', 'system');

        // Determine WebSocket protocol
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/console/${serverId}`;

        try {
            this.ws = new WebSocket(wsUrl);
            this.setupEventHandlers();
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.appendOutput(`Connection failed: ${error.message}\n`, 'error');
        }
    }

    /**
     * Setup WebSocket event handlers
     */
    setupEventHandlers() {
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.appendOutput('Connected to server console\n', 'system');
            this.appendOutput('─'.repeat(60) + '\n', 'system');
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.appendOutput('Connection error\n', 'error');
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket closed', event.code, event.reason);
            
            if (event.code !== 1000) { // Not a normal closure
                this.appendOutput('Connection closed\n', 'error');
                this.attemptReconnect();
            } else {
                this.appendOutput('Connection closed\n', 'system');
            }
        };
    }

    /**
     * Handle incoming WebSocket message
     */
    handleMessage(data) {
        switch (data.type) {
            case 'logs':
                // Initial logs dump
                this.appendOutput(data.data, 'log');
                break;
                
            case 'response':
                // Command response
                this.appendOutput(`\n> ${data.command}\n`, 'command');
                if (data.response) {
                    this.appendOutput(data.response + '\n', 'response');
                }
                break;
                
            case 'error':
                this.appendOutput(`Error: ${data.message}\n`, 'error');
                break;
                
            default:
                console.log('Unknown message type:', data.type);
        }
    }

    /**
     * Send command to server
     */
    sendCommand(command) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.appendOutput('Not connected to server\n', 'error');
            return false;
        }

        if (!command || !command.trim()) {
            return false;
        }

        try {
            this.ws.send(JSON.stringify({
                type: 'command',
                command: command.trim()
            }));
            return true;
        } catch (error) {
            console.error('Failed to send command:', error);
            this.appendOutput(`Failed to send command: ${error.message}\n`, 'error');
            return false;
        }
    }

    /**
     * Close console connection
     */
    close() {
        if (this.ws) {
            this.ws.close(1000, 'User closed console');
            this.ws = null;
        }

        document.getElementById('console-section').classList.add('hidden');
        this.serverId = null;
        this.reconnectAttempts = 0;
    }

    /**
     * Attempt to reconnect
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.appendOutput('Max reconnection attempts reached\n', 'error');
            return;
        }

        this.reconnectAttempts++;
        this.appendOutput(`Reconnecting (${this.reconnectAttempts}/${this.maxReconnectAttempts})...\n`, 'system');

        setTimeout(() => {
            if (this.serverId) {
                const serverName = document.getElementById('console-server-name').textContent;
                this.connect(this.serverId, serverName);
            }
        }, this.reconnectDelay);
    }

    /**
     * Append text to console output
     */
    appendOutput(text, type = 'log') {
        const output = document.getElementById('console-output');
        const console = document.getElementById('console');
        
        // Create colored span based on type
        const span = document.createElement('span');
        span.textContent = text;
        
        switch (type) {
            case 'command':
                span.style.color = '#00ffff'; // Cyan
                break;
            case 'response':
                span.style.color = '#ffff00'; // Yellow
                break;
            case 'error':
                span.style.color = '#ff0000'; // Red
                break;
            case 'system':
                span.style.color = '#888888'; // Gray
                break;
            default:
                span.style.color = '#00ff00'; // Green (default)
        }
        
        output.appendChild(span);
        
        // Auto-scroll to bottom
        console.scrollTop = console.scrollHeight;
    }

    /**
     * Clear console output
     */
    clearOutput() {
        const output = document.getElementById('console-output');
        output.textContent = '';
    }

    /**
     * Check if connected
     */
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Create global instance
window.consoleManager = new ConsoleManager();
