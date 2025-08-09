// Main JavaScript file for REST API MCP Tools Generator

class APIManager {
    constructor() {
        this.baseURL = '/api';
        this.init();
    }

    init() {
        this.setupEventListeners();
        // Wait for DOM to be fully ready before loading data
        $(document).ready(() => {
            this.loadInitialData();
        });
    }

    setupEventListeners() {
        // Wait for DOM to be ready
        $(document).ready(() => {
            // API Configuration Form
            $('#api-config-form').off('submit').on('submit', this.handleAPIConfigSubmit.bind(this));
            
            // Test Connection Button with multiple binding strategies
            $('#testSwaggerBtn').off('click').on('click', this.handleTestSwagger.bind(this));
            $(document).off('click', '#testSwaggerBtn').on('click', '#testSwaggerBtn', this.handleTestSwagger.bind(this));
            
            console.log('Test button found:', $('#testSwaggerBtn').length);
            console.log('Event listeners set up successfully');
        });
            
        // YAML generation - use event delegation for dynamically created buttons
        $(document).on('click', '.generate-yaml-btn', this.handleGenerateYAML.bind(this));
        
        // MCP Server management
        $(document).on('click', '.start-server-btn', this.handleStartServer.bind(this));
        $(document).on('click', '.stop-server-btn', this.handleStopServer.bind(this));
    }

    async loadInitialData() {
        console.log('Loading initial data...');
        try {
            await this.loadAPIConfigs();
            await this.loadYAMLFiles();
            await this.loadMCPServers();
            console.log('Initial data loading completed');
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }

    // API Configuration Methods
    async handleAPIConfigSubmit(e) {
        e.preventDefault();
        
        const formData = {
            name: $('#apiName').val(),
            swagger_url: $('#swaggerUrl').val(),
            api_base_url: $('#apiBaseUrl').val(),
            description: $('#apiDescription').val(),
            auth_type: $('#authType').val(),
            auth_config: {}
        };

        try {
            const response = await this.apiCall('POST', '/tools-generator/api-configs/', formData);
            this.showMessage('API Configuration saved successfully!', 'success');
            $('#api-config-form')[0].reset();
            await this.loadAPIConfigs();
        } catch (error) {
            this.showMessage('Error saving API configuration: ' + error.message, 'error');
        }
    }

    async handleTestSwagger(e) {
        console.log('handleTestSwagger called');
        e.preventDefault();
        
        const swaggerUrl = $('#swaggerUrl').val();
        const apiBaseUrl = $('#apiBaseUrl').val();
        
        console.log('Swagger URL:', swaggerUrl);
        console.log('API Base URL:', apiBaseUrl);
        
        if (!swaggerUrl) {
            this.showMessage('Please enter a Swagger URL', 'warning');
            return;
        }

        const testBtn = $('#testSwaggerBtn');
        const originalText = testBtn.html();
        testBtn.html('<span class="loading-spinner"></span> Testing...');
        testBtn.prop('disabled', true);

        try {
            const response = await this.apiCall('POST', '/tools-generator/swagger-test/test_swagger_url/', {
                swagger_url: swaggerUrl,
                api_base_url: apiBaseUrl
            });

            console.log('API Response:', response);

            if (response.status === 'success') {
                const message = `Successfully connected! Found ${response.swagger_info.endpoints_count} endpoints.`;
                console.log('Success message:', message);
                this.showMessage(message, 'success');
                
                // Auto-fill API name if empty
                if (!$('#apiName').val() && response.swagger_info.title) {
                    $('#apiName').val(response.swagger_info.title);
                }
            } else {
                const errorMessage = 'Connection failed: ' + response.message;
                console.log('Error message:', errorMessage);
                this.showMessage(errorMessage, 'error');
            }
        } catch (error) {
            const catchMessage = 'Error testing connection: ' + error.message;
            console.log('Catch message:', catchMessage);
            this.showMessage(catchMessage, 'error');
        } finally {
            testBtn.html(originalText);
            testBtn.prop('disabled', false);
        }
    }

    async loadAPIConfigs() {
        console.log('Loading API configs...');
        try {
            const configs = await this.apiCall('GET', '/tools-generator/api-configs/');
            console.log('API configs loaded:', configs);
            this.renderAPIConfigs(configs.results || configs);
        } catch (error) {
            console.error('Error loading API configs:', error);
        }
    }

    renderAPIConfigs(configs) {
        console.log('Rendering API configs:', configs);
        const container = $('#api-configs-list');
        console.log('Container found:', container.length);
        
        if (!configs || configs.length === 0) {
            container.html('<p class="text-muted">No API configurations found.</p>');
            return;
        }

        const html = configs.map(config => `
            <div class="api-config-item" data-id="${config.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${config.name}</h6>
                        <p class="mb-1 text-muted small">${config.api_base_url}</p>
                        <p class="mb-0 small">${config.description || 'No description'}</p>
                    </div>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary generate-yaml-btn" data-id="${config.id}">
                            <i class="fas fa-file-code"></i> Generate YAML
                        </button>
                        <button class="btn btn-outline-secondary test-config-btn" data-id="${config.id}">
                            <i class="fas fa-link"></i> Test
                        </button>
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-secondary">${config.auth_type}</span>
                    <span class="badge bg-info">${new Date(config.created_at).toLocaleDateString()}</span>
                </div>
            </div>
        `).join('');

        container.html(html);
    }

    // YAML Generation Methods
    async handleGenerateYAML(e) {
        console.log('handleGenerateYAML called');
        e.preventDefault();
        
        const configId = $(e.target).closest('.generate-yaml-btn').data('id');
        console.log('Config ID:', configId);
        
        if (!configId) {
            console.error('No config ID found');
            this.showMessage('Error: No configuration ID found', 'error');
            return;
        }
        
        const btn = $(e.target).closest('.generate-yaml-btn');
        const originalText = btn.html();
        
        btn.html('<span class="loading-spinner"></span> Generating...');
        btn.prop('disabled', true);

        try {
            const response = await this.apiCall('POST', `/tools-generator/api-configs/${configId}/generate_yaml/`);
            
            console.log('Generate YAML response:', response);
            
            if (response.status === 'success') {
                this.showMessage('YAML generation started successfully!', 'success');
                // Poll for completion
                setTimeout(() => this.loadYAMLFiles(), 2000);
            } else {
                this.showMessage('Error generating YAML: ' + response.message, 'error');
            }
        } catch (error) {
            console.error('Generate YAML error:', error);
            this.showMessage('Error generating YAML: ' + error.message, 'error');
        } finally {
            btn.html(originalText);
            btn.prop('disabled', false);
        }
    }

    async loadYAMLFiles() {
        try {
            const files = await this.apiCall('GET', '/tools-generator/yaml-files/');
            this.renderYAMLFiles(files.results || files);
        } catch (error) {
            console.error('Error loading YAML files:', error);
        }
    }

    renderYAMLFiles(files) {
        const container = $('#yaml-files-list');
        
        if (!files || files.length === 0) {
            container.html('<p class="text-muted">No YAML files generated yet.</p>');
            return;
        }

        const html = files.map(file => `
            <div class="yaml-file-item" data-id="${file.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${file.file_name}</h6>
                        <p class="mb-1 text-muted small">${file.api_config_name}</p>
                        <p class="mb-0 small">${file.tools_count} tools</p>
                    </div>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-success create-server-btn" data-id="${file.id}">
                            <i class="fas fa-server"></i> Create Server
                        </button>
                        <button class="btn btn-outline-primary download-yaml-btn" data-id="${file.id}">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-${this.getStatusColor(file.generation_status)}">${file.generation_status}</span>
                    <span class="badge bg-info">${new Date(file.created_at).toLocaleDateString()}</span>
                </div>
            </div>
        `).join('');

        container.html(html);

        // Add event listeners for new buttons
        $('.create-server-btn').on('click', this.handleCreateServer.bind(this));
        // Note: Download functionality to be implemented later
        $('.download-yaml-btn').on('click', function() {
            alert('Download functionality coming soon!');
        });
    }

    getStatusColor(status) {
        const colors = {
            'pending': 'warning',
            'processing': 'info',
            'completed': 'success',
            'failed': 'danger'
        };
        return colors[status] || 'secondary';
    }

    // MCP Server Methods
    async handleCreateServer(e) {
        const yamlFileId = $(e.target).closest('.create-server-btn').data('id');
        const serverName = prompt('Enter server name:');
        
        if (!serverName) return;

        try {
            const response = await this.apiCall('POST', '/mcp-server/registry/create_server_from_yaml/', {
                yaml_file_id: yamlFileId,
                server_name: serverName
            });

            if (response.status === 'success') {
                this.showMessage(`MCP Server "${serverName}" created successfully!`, 'success');
                await this.loadMCPServers();
            } else {
                this.showMessage('Error creating server: ' + response.message, 'error');
            }
        } catch (error) {
            this.showMessage('Error creating server: ' + error.message, 'error');
        }
    }

    async loadMCPServers() {
        try {
            const servers = await this.apiCall('GET', '/mcp-server/instances/');
            this.renderMCPServers(servers.results || servers);
        } catch (error) {
            console.error('Error loading MCP servers:', error);
        }
    }

    renderMCPServers(servers) {
        const container = $('#mcp-servers-list');
        
        if (!servers || servers.length === 0) {
            container.html('<p class="text-muted">No MCP servers created yet.</p>');
            return;
        }

        const html = servers.map(server => `
            <div class="mcp-server-item" data-id="${server.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">
                            <span class="status-indicator status-${server.is_running ? 'running' : 'stopped'}"></span>
                            ${server.server_name}
                        </h6>
                        <p class="mb-1 text-muted small">${server.api_config_name}</p>
                        <p class="mb-0 small">YAML: ${server.yaml_file_name}</p>
                    </div>
                    <div class="btn-group btn-group-sm">
                        ${server.is_running ? 
                            `<button class="btn btn-outline-danger stop-server-btn" data-id="${server.id}">
                                <i class="fas fa-stop"></i> Stop
                            </button>
                            <button class="btn btn-outline-info view-tools-btn" data-id="${server.id}">
                                <i class="fas fa-tools"></i> Tools
                            </button>` :
                            `<button class="btn btn-outline-success start-server-btn" data-id="${server.id}">
                                <i class="fas fa-play"></i> Start
                            </button>`
                        }
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-${server.is_running ? 'success' : 'secondary'}">
                        ${server.is_running ? 'Running' : 'Stopped'}
                    </span>
                    <span class="badge bg-info">${new Date(server.created_at).toLocaleDateString()}</span>
                </div>
            </div>
        `).join('');

        container.html(html);

        // Add event listeners
        $('.view-tools-btn').on('click', this.handleViewTools.bind(this));
    }

    async handleStartServer(e) {
        const serverId = $(e.target).closest('.start-server-btn').data('id');
        
        try {
            const response = await this.apiCall('POST', `/mcp-server/instances/${serverId}/start_server/`);
            
            if (response.status === 'success') {
                this.showMessage('Server started successfully!', 'success');
                await this.loadMCPServers();
            } else {
                this.showMessage('Error starting server: ' + response.message, 'error');
            }
        } catch (error) {
            this.showMessage('Error starting server: ' + error.message, 'error');
        }
    }

    async handleStopServer(e) {
        const serverId = $(e.target).closest('.stop-server-btn').data('id');
        
        try {
            const response = await this.apiCall('POST', `/mcp-server/instances/${serverId}/stop_server/`);
            
            if (response.status === 'success') {
                this.showMessage('Server stopped successfully!', 'success');
                await this.loadMCPServers();
            } else {
                this.showMessage('Error stopping server: ' + response.message, 'error');
            }
        } catch (error) {
            this.showMessage('Error stopping server: ' + error.message, 'error');
        }
    }

    async handleViewTools(e) {
        const serverId = $(e.target).closest('.view-tools-btn').data('id');
        
        try {
            const response = await this.apiCall('GET', `/mcp-server/instances/${serverId}/get_tools/`);
            
            if (response.status === 'success') {
                this.showToolsModal(response.tools);
            } else {
                this.showMessage('Error loading tools: ' + response.message, 'error');
            }
        } catch (error) {
            this.showMessage('Error loading tools: ' + error.message, 'error');
        }
    }

    showToolsModal(tools) {
        const html = tools.map(tool => `
            <div class="tool-item border rounded p-3 mb-2">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${tool.name}</h6>
                        <p class="mb-1 small text-muted">${tool.method} ${tool.path}</p>
                        <p class="mb-0 small">${tool.description || 'No description'}</p>
                    </div>
                    <button class="btn btn-sm btn-outline-primary test-tool-btn" 
                            data-tool-name="${tool.name}" data-tool='${JSON.stringify(tool)}'>
                        <i class="fas fa-play"></i> Test
                    </button>
                </div>
            </div>
        `).join('');

        // Create and show modal
        const modal = $(`
            <div class="modal fade" id="toolsModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Available Tools</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            ${html}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `);

        $('body').append(modal);
        modal.modal('show');

        // Remove modal when hidden
        modal.on('hidden.bs.modal', function() {
            modal.remove();
        });
    }

    // Utility Methods
    async apiCall(method, endpoint, data = null) {
        const config = {
            method: method,
            url: this.baseURL + endpoint,
            headers: {
                'Content-Type': 'application/json',
            }
        };

        if (data) {
            config.data = data;
        }

        try {
            const response = await axios(config);
            return response.data;
        } catch (error) {
            if (error.response) {
                throw new Error(error.response.data.message || 'Server error');
            } else {
                throw new Error('Network error');
            }
        }
    }

    showMessage(message, type) {
        console.log('showMessage called:', message, type);
        
        const alertClass = type === 'success' ? 'alert-success' : 
                          type === 'error' ? 'alert-danger' : 
                          type === 'warning' ? 'alert-warning' : 'alert-info';

        console.log('Alert class:', alertClass);
        
        const alert = $(`
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert" style="margin-bottom: 1rem;">
                <strong>${type === 'success' ? '✅ Success:' : type === 'error' ? '❌ Error:' : type === 'warning' ? '⚠️  Warning:' : 'ℹ️  Info:'}</strong> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `);

        console.log('Status messages container found:', $('#status-messages').length);
        
        // Clear previous messages of the same type to avoid clutter
        $(`#status-messages .alert-${alertClass.split('-')[1]}`).remove();
        
        $('#status-messages').prepend(alert);
        console.log('Alert appended');

        // Scroll to top to ensure message is visible
        $('html, body').animate({ scrollTop: 0 }, 300);

        // Auto-remove after 8 seconds (longer for better UX)
        setTimeout(() => {
            alert.fadeOut(300, function() {
                $(this).remove();
            });
        }, 8000);
    }
}

// Initialize the application when the page loads
$(document).ready(function() {
    window.apiManager = new APIManager();
    
    // Backup function for direct onclick
    window.testSwaggerClick = function() {
        console.log('Direct onclick called');
        alert('Direct onclick works!');
        if (window.apiManager) {
            window.apiManager.handleTestSwagger({preventDefault: function(){}});
        }
    };
});
