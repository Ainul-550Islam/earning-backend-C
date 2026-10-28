// Backup Admin JavaScript

// Global variables
let backupStats = {};
let activeBackups = [];
let refreshInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeBackupAdmin();
});

function initializeBackupAdmin() {
    loadBackupStats();
    loadActiveBackups();
    setupEventListeners();
    startAutoRefresh();
}

// Load backup statistics
function loadBackupStats() {
    fetch('/api/backup/dashboard-stats/')
        .then(response => response.json())
        .then(data => {
            backupStats = data;
            updateStatsDisplay();
        })
        .catch(error => {
            console.error('Error loading backup stats:', error);
            showNotification('Error loading backup statistics', 'error');
        });
}

// Load active backups
function loadActiveBackups() {
    fetch('/api/backup/backups/?status=running,pending,verifying')
        .then(response => response.json())
        .then(data => {
            activeBackups = data.results || [];
            updateActiveBackupsDisplay();
        })
        .catch(error => {
            console.error('Error loading active backups:', error);
        });
}

// Update statistics display
function updateStatsDisplay() {
    const statsContainer = document.getElementById('backup-stats');
    if (!statsContainer) return;

    const html = `
        <div class="backup-stats-grid">
            <div class="stat-card">
                <h3>Total Backups</h3>
                <div class="stat-value">${backupStats.total_backups || 0}</div>
                <div class="stat-label">All time</div>
            </div>
            <div class="stat-card">
                <h3>Successful</h3>
                <div class="stat-value status-healthy">${backupStats.successful_backups || 0}</div>
                <div class="stat-label">Last 30 days</div>
            </div>
            <div class="stat-card">
                <h3>Failed</h3>
                <div class="stat-value status-error">${backupStats.failed_backups || 0}</div>
                <div class="stat-label">Last 30 days</div>
            </div>
            <div class="stat-card">
                <h3>Success Rate</h3>
                <div class="stat-value">${(backupStats.success_rate || 0).toFixed(1)}%</div>
                <div class="stat-label">Last 30 days</div>
            </div>
            <div class="stat-card">
                <h3>Storage Used</h3>
                <div class="stat-value">${(backupStats.storage_utilization || 0).toFixed(1)}%</div>
                <div class="stat-label">Current usage</div>
            </div>
            <div class="stat-card">
                <h3>Last Backup</h3>
                <div class="stat-value">${formatDateTime(backupStats.last_backup_time)}</div>
                <div class="stat-label">Most recent</div>
            </div>
        </div>
    `;
    
    statsContainer.innerHTML = html;
}

// Update active backups display
function updateActiveBackupsDisplay() {
    const activeContainer = document.getElementById('active-backups');
    if (!activeContainer) return;

    if (activeBackups.length === 0) {
        activeContainer.innerHTML = '<p class="text-muted">No active backups</p>';
        return;
    }

    const html = activeBackups.map(backup => `
        <div class="backup-item">
            <div class="backup-info">
                <div class="backup-name">${backup.name}</div>
                <div class="backup-meta">
                    Type: ${backup.backup_type} | 
                    Status: <span class="status-badge status-${backup.status}">${backup.status}</span> |
                    Started: ${formatDateTime(backup.start_time)}
                </div>
            </div>
            <div class="backup-actions">
                ${backup.status === 'running' ? 
                    `<button class="btn-backup btn-warning" onclick="cancelBackup('${backup.id}')">
                        <span class="icon-settings"></span> Cancel
                    </button>` : ''
                }
                <button class="btn-backup btn-secondary" onclick="viewBackupLogs('${backup.id}')">
                    <span class="icon-backup"></span> Logs
                </button>
            </div>
        </div>
    `).join('');

    activeContainer.innerHTML = html;
}

// Setup event listeners
function setupEventListeners() {
    // Manual backup button
    const startBackupBtn = document.getElementById('start-backup-btn');
    if (startBackupBtn) {
        startBackupBtn.addEventListener('click', startManualBackup);
    }

    // Refresh buttons
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', manualRefresh);
    }

    // Schedule form
    const scheduleForm = document.getElementById('schedule-form');
    if (scheduleForm) {
        scheduleForm.addEventListener('submit', handleScheduleSubmit);
    }
}

// Start manual backup
function startManualBackup() {
    const btn = document.getElementById('start-backup-btn');
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<span class="loading"></span> Starting...';
    btn.disabled = true;

    const backupData = {
        backup_type: 'manual',
        name: document.getElementById('backup-name').value,
        description: document.getElementById('backup-description').value,
        storage_type: document.getElementById('storage-type').value,
        encrypt: document.getElementById('encrypt-backup').checked,
        compress: document.getElementById('compress-backup').checked
    };

    fetch('/api/backup/start-backup/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(backupData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Backup started successfully', 'success');
            loadActiveBackups();
            loadBackupStats();
        } else {
            showNotification(data.message || 'Failed to start backup', 'error');
        }
    })
    .catch(error => {
        console.error('Error starting backup:', error);
        showNotification('Error starting backup', 'error');
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

// Cancel backup
function cancelBackup(backupId) {
    if (!confirm('Are you sure you want to cancel this backup?')) {
        return;
    }

    fetch(`/api/backup/cancel-backup/${backupId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Backup cancelled', 'warning');
            loadActiveBackups();
        } else {
            showNotification(data.message || 'Failed to cancel backup', 'error');
        }
    })
    .catch(error => {
        console.error('Error cancelling backup:', error);
        showNotification('Error cancelling backup', 'error');
    });
}

// View backup logs
function viewBackupLogs(backupId) {
    window.open(`/api/backup/backups/${backupId}/logs/`, '_blank');
}

// Handle schedule form submission
function handleScheduleSubmit(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const scheduleData = {
        name: formData.get('name'),
        frequency: formData.get('frequency'),
        cron_expression: formData.get('cron_expression'),
        backup_type: formData.get('backup_type'),
        storage_type: formData.get('storage_type'),
        is_active: formData.get('is_active') === 'on'
    };

    fetch('/api/backup/schedules/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(scheduleData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.id) {
            showNotification('Schedule created successfully', 'success');
            event.target.reset();
        } else {
            showNotification(data.message || 'Failed to create schedule', 'error');
        }
    })
    .catch(error => {
        console.error('Error creating schedule:', error);
        showNotification('Error creating schedule', 'error');
    });
}

// Auto refresh
function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        loadActiveBackups();
        loadBackupStats();
    }, 30000); // Refresh every 30 seconds
}

// Manual refresh
function manualRefresh() {
    loadActiveBackups();
    loadBackupStats();
    showNotification('Data refreshed', 'success');
}

// Utility functions
function formatDateTime(dateTimeString) {
    if (!dateTimeString) return 'Never';
    
    const date = new Date(dateTimeString);
    return date.toLocaleString();
}

function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        padding: 15px 20px;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        max-width: 300px;
        word-wrap: break-word;
    `;
    
    notification.innerHTML = `
        <button type="button" class="close" onclick="this.parentElement.remove()" style="
            position: absolute;
            top: 5px;
            right: 10px;
            background: none;
            border: none;
            font-size: 16px;
            cursor: pointer;
        ">×</button>
        ${message}
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Progress tracking
function updateBackupProgress(backupId, progress, status) {
    const progressBar = document.getElementById(`progress-${backupId}`);
    if (progressBar) {
        const fill = progressBar.querySelector('.progress-fill');
        if (fill) {
            fill.style.width = `${progress}%`;
        }
        
        const statusText = progressBar.querySelector('.progress-status');
        if (statusText) {
            statusText.textContent = status;
        }
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});
