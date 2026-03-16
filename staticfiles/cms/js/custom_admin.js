// Custom Admin JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Add custom classes to tables
    const tables = document.querySelectorAll('table');
    tables.forEach(table => {
        table.classList.add('table', 'table-hover', 'table-striped');
    });
    
    // Add status badges
    addStatusBadges();
    
    // Add action buttons styling
    styleActionButtons();
    
    // Add filter toggler
    addFilterToggler();
    
    // Add quick stats to dashboard
    if (document.body.classList.contains('dashboard')) {
        addDashboardStats();
    }
    
    // Add image preview on hover
    addImagePreviews();
    
    // Add JSON field formatter
    formatJSONFields();
});

function addStatusBadges() {
    // Find status cells and add badges
    document.querySelectorAll('td.field-status, td.field-is_active, td.field-is_featured').forEach(cell => {
        const text = cell.textContent.trim();
        const statusClass = getStatusClass(text);
        cell.innerHTML = `<span class="status-badge ${statusClass}">${text}</span>`;
    });
}

function getStatusClass(status) {
    const statusMap = {
        'published': 'status-published',
        'draft': 'status-draft',
        'scheduled': 'status-scheduled',
        'archived': 'status-archived',
        'True': 'status-published',
        'False': 'status-draft',
        'active': 'status-published',
        'inactive': 'status-draft'
    };
    return statusMap[status] || 'status-draft';
}

function styleActionButtons() {
    // Style action buttons in tables
    document.querySelectorAll('.changelist-actions a').forEach(link => {
        if (link.textContent.includes('Add')) {
            link.classList.add('btn-admin', 'btn-admin-primary', 'icon-add');
        }
    });
    
    // Style object tools
    document.querySelectorAll('.object-tools a').forEach(link => {
        link.classList.add('btn-admin', 'btn-admin-primary');
    });
}

function addFilterToggler() {
    // Add toggle button for filters on mobile
    const filterTitle = document.querySelector('#changelist-filter h2');
    if (filterTitle) {
        const toggleBtn = document.createElement('button');
        toggleBtn.innerHTML = '⚙️ Filters';
        toggleBtn.classList.add('btn-admin', 'btn-admin-warning', 'filter-toggle');
        toggleBtn.style.marginBottom = '10px';
        
        toggleBtn.addEventListener('click', function() {
            const filterContent = document.querySelector('#changelist-filter');
            filterContent.style.display = filterContent.style.display === 'none' ? 'block' : 'none';
        });
        
        filterTitle.parentNode.insertBefore(toggleBtn, filterTitle);
    }
}

function addDashboardStats() {
    // Create dashboard stats cards
    const contentMain = document.querySelector('#content-main');
    if (contentMain) {
        const statsHTML = `
            <div class="dashboard-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px;">
                <div class="dashboard-card content-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h3>Total Content</h3>
                            <div class="stat-number">0</div>
                            <div class="stat-label">Published Pages</div>
                        </div>
                        <div class="stat-icon">📄</div>
                    </div>
                </div>
                <div class="dashboard-card banner-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h3>Active Banners</h3>
                            <div class="stat-number">0</div>
                            <div class="stat-label">Running Campaigns</div>
                        </div>
                        <div class="stat-icon">🎯</div>
                    </div>
                </div>
                <div class="dashboard-card faq-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h3>FAQ Articles</h3>
                            <div class="stat-number">0</div>
                            <div class="stat-label">Help Articles</div>
                        </div>
                        <div class="stat-icon">❓</div>
                    </div>
                </div>
                <div class="dashboard-card category-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h3>Categories</h3>
                            <div class="stat-number">0</div>
                            <div class="stat-label">Content Groups</div>
                        </div>
                        <div class="stat-icon">📂</div>
                    </div>
                </div>
            </div>
        `;
        
        contentMain.insertAdjacentHTML('afterbegin', statsHTML);
        
        // Fetch stats via AJAX
        fetchDashboardStats();
    }
}

function fetchDashboardStats() {
    // You would typically make an AJAX call here
    // For now, we'll simulate with random numbers
    setTimeout(() => {
        document.querySelectorAll('.stat-number').forEach((stat, index) => {
            const numbers = [42, 18, 56, 12];
            animateCounter(stat, numbers[index]);
        });
    }, 500);
}

function animateCounter(element, target) {
    let current = 0;
    const increment = target / 50;
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        element.textContent = Math.floor(current);
    }, 20);
}

function addImagePreviews() {
    // Add image preview on hover for thumbnail fields
    document.querySelectorAll('.field-thumbnail img, .field-image img').forEach(img => {
        const preview = document.createElement('div');
        preview.className = 'image-preview-modal';
        preview.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            display: none;
            z-index: 10000;
            background: white;
            padding: 10px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        `;
        
        const previewImg = document.createElement('img');
        previewImg.src = img.src;
        previewImg.style.maxWidth = '500px';
        previewImg.style.maxHeight = '500px';
        preview.appendChild(previewImg);
        
        document.body.appendChild(preview);
        
        img.addEventListener('mouseenter', () => {
            preview.style.display = 'block';
        });
        
        img.addEventListener('mouseleave', () => {
            preview.style.display = 'none';
        });
    });
}

function formatJSONFields() {
    // Format JSON fields for better readability
    document.querySelectorAll('.json-field').forEach(field => {
        try {
            const jsonData = JSON.parse(field.textContent);
            field.textContent = JSON.stringify(jsonData, null, 2);
            field.style.whiteSpace = 'pre-wrap';
        } catch(e) {
            // Not valid JSON
        }
    });
}

// Add keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl + / for search focus
    if (e.ctrlKey && e.key === '/') {
        e.preventDefault();
        const searchInput = document.querySelector('#searchbar');
        if (searchInput) searchInput.focus();
    }
    
    // Ctrl + N for new item
    if (e.ctrlKey && e.key === 'n') {
        e.preventDefault();
        const addButton = document.querySelector('.addlink');
        if (addButton) addButton.click();
    }
});