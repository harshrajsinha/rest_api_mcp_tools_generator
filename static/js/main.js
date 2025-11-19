// Main JavaScript file for REST API MCP Tools Generator

class UIManager {
    static showToast(message, type = 'info') {
        const icon = type === 'success' ? 'fa-check-circle' :
            type === 'error' ? 'fa-exclamation-circle' :
                type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle';

        const bgClass = type === 'success' ? 'text-success' :
            type === 'error' ? 'text-danger' :
                type === 'warning' ? 'text-warning' : 'text-primary';

        const toastHtml = `
            <div class="toast fade show" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="fas ${icon} ${bgClass} me-2"></i>
                    <strong class="me-auto text-capitalize">${type}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;

        const toastEl = $(toastHtml);
        $('.toast-container').append(toastEl);

        // Auto remove
        setTimeout(() => {
            toastEl.removeClass('show');
            setTimeout(() => toastEl.remove(), 300);
        }, 5000);
    }

    static showSpinner(element, text = 'Loading...') {
        const originalContent = element.html();
        element.data('original-content', originalContent);
        element.html(`<span class="spinner-border spinner-border-sm me-2"></span>${text}`);
        element.prop('disabled', true);
    }

    static hideSpinner(element) {
        const originalContent = element.data('original-content');
        if (originalContent) {
            element.html(originalContent);
        }
        element.prop('disabled', false);
    }
}

class WizardManager {
    constructor(apiManager) {
        this.apiManager = apiManager;
        this.currentStep = 1;
        this.formData = {};
        this.init();
    }

    init() {
        // Step 1: Test Connection
        $('#step1-form').on('submit', async (e) => {
            e.preventDefault();
            await this.handleStep1();
        });

        // Step 2: Configure
        $('#step2-form').on('submit', (e) => {
            e.preventDefault();
            this.handleStep2();
        });

        // Step 3: Create
        $('#createApiBtn').on('click', () => this.handleStep3());

        // Navigation
        $('.prev-step').on('click', () => this.goToStep(this.currentStep - 1));

        // Auth Type Change
        $('#authType').on('change', (e) => this.handleAuthTypeChange(e.target.value));
    }

    async handleStep1() {
        const btn = $('#testConnectionBtn');
        const swaggerUrl = $('#swaggerUrl').val();

        if (!swaggerUrl) {
            UIManager.showToast('Please enter a Swagger URL', 'warning');
            return;
        }

        UIManager.showSpinner(btn, 'Testing Connection...');

        try {
            const response = await this.apiManager.apiCall('POST', '/tools-generator/swagger-test/test_swagger_url/', {
                swagger_url: swaggerUrl
            });

            if (response.status === 'success') {
                this.formData.swaggerUrl = swaggerUrl;
                this.formData.swaggerInfo = response.swagger_info;

                // Auto-fill Step 2
                $('#apiName').val(response.swagger_info.title || '');
                $('#apiBaseUrl').val(response.swagger_info.host ? `https://${response.swagger_info.host}${response.swagger_info.base_path}` : '');
                $('#apiDescription').val(response.swagger_info.description || '');

                UIManager.showToast('Connection successful!', 'success');
                this.goToStep(2);
            }
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        } finally {
            UIManager.hideSpinner(btn);
        }
    }

    handleStep2() {
        this.formData.name = $('#apiName').val();
        this.formData.baseUrl = $('#apiBaseUrl').val();
        this.formData.description = $('#apiDescription').val();
        this.formData.authType = $('#authType').val();

        // Collect Auth Config
        this.formData.authConfig = {};
        $('#authConfigFields input').each((_, el) => {
            this.formData.authConfig[el.name] = $(el).val();
        });

        this.updateReviewStep();
        this.goToStep(3);
    }

    async handleStep3() {
        const btn = $('#createApiBtn');
        UIManager.showSpinner(btn, 'Creating...');

        try {
            const payload = {
                name: this.formData.name,
                swagger_url: this.formData.swaggerUrl,
                api_base_url: this.formData.baseUrl,
                description: this.formData.description,
                auth_type: this.formData.authType,
                auth_config: this.formData.authConfig
            };

            await this.apiManager.apiCall('POST', '/tools-generator/api-configs/', payload);

            UIManager.showToast('API Configuration created successfully!', 'success');
            $('#createApiModal').modal('hide');
            this.resetWizard();
            this.apiManager.loadAPIConfigs();
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        } finally {
            UIManager.hideSpinner(btn);
        }
    }

    goToStep(step) {
        this.currentStep = step;

        // Update UI
        $('.step-content').addClass('d-none');
        $(`#step${step}`).removeClass('d-none');

        // Update Wizard Header
        $('.wizard-step').removeClass('active completed');
        for (let i = 1; i < step; i++) {
            $(`.wizard-step[data-step="${i}"]`).addClass('completed');
        }
        $(`.wizard-step[data-step="${step}"]`).addClass('active');
    }

    updateReviewStep() {
        $('#reviewName').text(this.formData.name);
        $('#reviewSwagger').text(this.formData.swaggerUrl);
        $('#reviewBaseUrl').text(this.formData.baseUrl);
        $('#reviewAuth').html(`<span class="badge bg-secondary">${this.formData.authType}</span>`);
        $('#reviewEndpointsCount').text(`${this.formData.swaggerInfo?.endpoints_count || 0} endpoints found`);
    }

    handleAuthTypeChange(type) {
        const container = $('#authConfigFields');
        container.empty();

        if (type === 'api_key') {
            container.html(`
                <div class="row g-3">
                    <div class="col-md-6">
                        <label class="form-label small">Header Name</label>
                        <input type="text" class="form-control" name="header_name" placeholder="X-API-Key" required>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small">API Key</label>
                        <input type="password" class="form-control" name="api_key" required>
                    </div>
                </div>
            `);
        } else if (type === 'bearer_token') {
            container.html(`
                <div class="mb-2">
                    <label class="form-label small">Token</label>
                    <input type="password" class="form-control" name="token" required>
                </div>
            `);
        }
        // Add other auth types as needed
    }

    resetWizard() {
        this.currentStep = 1;
        this.formData = {};
        $('#step1-form')[0].reset();
        $('#step2-form')[0].reset();
        this.goToStep(1);
    }
}

class APIManager {
    constructor() {
        this.baseURL = '/api';
        this.init();
    }

    init() {
        this.wizard = new WizardManager(this);
        this.loadInitialData();
        this.setupGlobalListeners();
    }

    setupGlobalListeners() {
        // Refresh buttons
        $(document).on('click', '.refresh-btn', () => this.loadInitialData());

        // Generate YAML
        $(document).on('click', '.generate-yaml-btn', this.handleGenerateYAML.bind(this));

        // Tool Actions
        $(document).on('click', '.download-yaml-btn', this.handleDownloadMCPPackage.bind(this));

        // Installer Download
        $(document).on('click', '.download-installer-btn', this.handleDownloadInstaller.bind(this));

        // Delete Actions
        $(document).on('click', '.delete-config-btn', this.handleDeleteConfig.bind(this));
        $(document).on('click', '.delete-yaml-btn', this.handleDeleteYAML.bind(this));
    }

    async loadInitialData() {
        await Promise.all([
            this.loadAPIConfigs(),
            this.loadYAMLFiles()
        ]);
    }

    async apiCall(method, endpoint, data = null) {
        try {
            const config = {
                method,
                url: this.baseURL + endpoint,
                headers: { 'Content-Type': 'application/json' },
                data
            };
            const response = await axios(config);
            return response.data;
        } catch (error) {
            throw new Error(error.response?.data?.message || 'Network error');
        }
    }

    // --- API Configs ---
    async loadAPIConfigs() {
        try {
            const response = await this.apiCall('GET', '/tools-generator/api-configs/');
            this.renderAPIConfigs(response.results || response);
        } catch (error) {
            console.error('Error loading configs:', error);
            $('#api-configs-list').html(this.getErrorState('Failed to load API configurations'));
        }
    }

    renderAPIConfigs(configs) {
        const container = $('#api-configs-list');
        if (!configs.length) {
            container.html(this.getEmptyState('No API configurations yet. Create one to get started!'));
            return;
        }

        container.html(configs.map(config => `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <h5 class="card-title mb-0 text-truncate" title="${config.name}">${config.name}</h5>
                            <span class="badge bg-secondary">${config.auth_type}</span>
                        </div>
                        <p class="card-text text-muted small mb-3 text-truncate">${config.api_base_url}</p>
                        <div class="d-grid gap-2">
                            <button class="btn btn-outline-primary btn-sm generate-yaml-btn" data-id="${config.id}">
                                <i class="fas fa-file-code me-2"></i> Generate Tools
                            </button>
                            <button class="btn btn-outline-danger btn-sm delete-config-btn" data-id="${config.id}" data-name="${config.name}">
                                <i class="fas fa-trash me-2"></i> Delete Configuration
                            </button>
                        </div>
                    </div>
                    <div class="card-footer bg-transparent border-top-0 text-muted small">
                        Created ${new Date(config.created_at).toLocaleDateString()}
                    </div>
                </div>
            </div>
        `).join(''));
    }

    // --- YAML Files ---
    async loadYAMLFiles() {
        try {
            const response = await this.apiCall('GET', '/tools-generator/yaml-files/');
            this.renderYAMLFiles(response.results || response);
        } catch (error) {
            console.error('Error loading YAMLs:', error);
        }
    }

    renderYAMLFiles(files) {
        const container = $('#yaml-files-list');
        if (!files.length) {
            container.html(this.getEmptyState('No tool definitions generated yet.'));
            return;
        }

        container.html(files.map(file => `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <h5 class="card-title mb-0 text-truncate">${file.file_name}</h5>
                            <span class="badge bg-info">${file.tools_count} tools</span>
                        </div>
                        <p class="text-muted small mb-3">From: ${file.api_config_name}</p>
                        <div class="d-grid gap-2">
                            <button class="btn btn-primary btn-sm download-installer-btn" data-yaml-id="${file.id}">
                                <i class="fas fa-rocket me-2"></i> Download Auto-Installer
                            </button>
                            <a href="/enhance-endpoints/?yaml_file=${file.id}" class="btn btn-outline-primary btn-sm">
                                <i class="fas fa-magic me-1"></i> Enhance Descriptions
                            </a>
                            <div class="btn-group">
                                <button class="btn btn-outline-secondary btn-sm download-yaml-btn" data-id="${file.id}">
                                    <i class="fas fa-download me-1"></i> Package
                                </button>
                                <button class="btn btn-outline-danger btn-sm delete-yaml-btn" data-id="${file.id}" data-name="${file.file_name}">
                                    <i class="fas fa-trash me-1"></i> Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `).join(''));
    }

    // --- MCP Servers ---
    async loadMCPServers() {
        try {
            const response = await this.apiCall('GET', '/mcp-server/instances/');
            this.renderMCPServers(response.results || response);
        } catch (error) {
            console.error('Error loading servers:', error);
        }
    }

    renderMCPServers(servers) {
        const container = $('#mcp-servers-list');
        if (!servers.length) {
            container.html(this.getEmptyState('No servers running.'));
            return;
        }

        container.html(servers.map(server => `
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card h-100 border-${server.is_running ? 'success' : 'secondary'}">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="card-title mb-0">${server.server_name}</h5>
                            <span class="status-indicator status-${server.is_running ? 'running' : 'stopped'}"></span>
                        </div>
                        <p class="text-muted small mb-3">Config: ${server.yaml_file_name}</p>
                        <div class="d-grid gap-2">
                            <button class="btn btn-primary btn-sm download-installer-btn" data-id="${server.id}">
                                <i class="fas fa-rocket me-2"></i> Download Auto-Installer
                            </button>
                            ${server.is_running ?
                `<button class="btn btn-danger btn-sm stop-server-btn" data-id="${server.id}">
                                    <i class="fas fa-stop me-2"></i> Stop Server
                                </button>` :
                `<button class="btn btn-success btn-sm start-server-btn" data-id="${server.id}">
                                    <i class="fas fa-play me-2"></i> Start Server
                                </button>`
            }
                        </div>
                    </div>
                </div>
            </div>
        `).join(''));
    }

    // --- Actions ---
    async handleGenerateYAML(e) {
        const btn = $(e.currentTarget);
        const id = btn.data('id');

        UIManager.showSpinner(btn, 'Generating...');

        try {
            await this.apiCall('POST', `/tools-generator/api-configs/${id}/generate_yaml/`);
            UIManager.showToast('Generation started', 'success');
            setTimeout(() => this.loadYAMLFiles(), 2000);
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        } finally {
            UIManager.hideSpinner(btn);
        }
    }

    async handleCreateServer(e) {
        const id = $(e.currentTarget).data('id');
        const name = prompt('Enter a name for this server instance:');
        if (!name) return;

        try {
            await this.apiCall('POST', '/mcp-server/registry/create_server_from_yaml/', {
                yaml_file_id: id,
                server_name: name
            });
            UIManager.showToast('Server created', 'success');
            this.loadMCPServers();
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        }
    }

    async handleStartServer(e) {
        const id = $(e.currentTarget).data('id');
        try {
            await this.apiCall('POST', `/mcp-server/instances/${id}/start_server/`);
            UIManager.showToast('Server started', 'success');
            this.loadMCPServers();
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        }
    }

    async handleStopServer(e) {
        const id = $(e.currentTarget).data('id');
        try {
            await this.apiCall('POST', `/mcp-server/instances/${id}/stop_server/`);
            UIManager.showToast('Server stopped', 'success');
            this.loadMCPServers();
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        }
    }

    async handleDownloadMCPPackage(e) {
        const yamlFileId = $(e.currentTarget).data('id');
        const serverName = prompt('Enter server name for the MCP package:', `mcp_server_${yamlFileId}`);

        if (!serverName) return;

        const btn = $(e.currentTarget);
        UIManager.showSpinner(btn, '');

        try {
            const response = await fetch('/api/mcp-server/registry/download_mcp_package/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    yaml_file_id: yamlFileId,
                    server_name: serverName
                })
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;

                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = `${serverName}_mcp_package.zip`;
                if (contentDisposition) {
                    const matches = /filename="([^"]*)"/.exec(contentDisposition);
                    if (matches) filename = matches[1];
                }
                a.download = filename;

                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                UIManager.showToast('Package downloaded successfully!', 'success');
            } else {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Download failed');
            }
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        } finally {
            UIManager.hideSpinner(btn);
        }
    }

    async handleDownloadInstaller(e) {
        const yamlId = $(e.currentTarget).data('yaml-id');
        const btn = $(e.currentTarget);

        if (!yamlId) {
            UIManager.showToast('YAML file ID not found', 'error');
            return;
        }

        UIManager.showSpinner(btn, 'Generating...');

        try {
            // Call the new generate_installer endpoint on the YAML file
            const response = await fetch(`/api/tools-generator/yaml-files/${yamlId}/generate_installer/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;

                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'mcp_installer.zip';
                if (contentDisposition) {
                    const matches = /filename="([^"]*)"/.exec(contentDisposition);
                    if (matches) filename = matches[1];
                }
                a.download = filename;

                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                UIManager.showToast('Auto-installer downloaded! Extract and run install script.', 'success');
            } else {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Download failed');
            }
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        } finally {
            UIManager.hideSpinner(btn);
        }
    }

    async handleDeleteConfig(e) {
        const id = $(e.currentTarget).data('id');
        const name = $(e.currentTarget).data('name');

        if (!confirm(`Are you sure you want to delete the API configuration "${name}"?\n\nThis action cannot be undone.`)) {
            return;
        }

        const btn = $(e.currentTarget);
        UIManager.showSpinner(btn, 'Deleting...');

        try {
            await this.apiCall('DELETE', `/tools-generator/api-configs/${id}/`);
            UIManager.showToast(`Configuration "${name}" deleted successfully`, 'success');
            this.loadAPIConfigs();
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        } finally {
            UIManager.hideSpinner(btn);
        }
    }

    async handleDeleteYAML(e) {
        const id = $(e.currentTarget).data('id');
        const name = $(e.currentTarget).data('name');

        if (!confirm(`Are you sure you want to delete the tool definition "${name}"?\n\nThis action cannot be undone.`)) {
            return;
        }

        const btn = $(e.currentTarget);
        UIManager.showSpinner(btn, 'Deleting...');

        try {
            await this.apiCall('DELETE', `/tools-generator/yaml-files/${id}/`);
            UIManager.showToast(`Tool definition "${name}" deleted successfully`, 'success');
            this.loadYAMLFiles();
        } catch (error) {
            UIManager.showToast(error.message, 'error');
        } finally {
            UIManager.hideSpinner(btn);
        }
    }

    // --- Helpers ---
    getEmptyState(message) {
        return `
            <div class="col-12">
                <div class="empty-state">
                    <div class="empty-state-icon"><i class="fas fa-wind"></i></div>
                    <p>${message}</p>
                </div>
            </div>
        `;
    }

    getErrorState(message) {
        return `
            <div class="col-12 text-center text-danger py-4">
                <i class="fas fa-exclamation-circle mb-2"></i>
                <p>${message}</p>
            </div>
        `;
    }

    getCSRFToken() {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, 10) === 'csrftoken=') {
                    cookieValue = decodeURIComponent(cookie.substring(10));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// Initialize
$(document).ready(() => {
    window.apiManager = new APIManager();
});
