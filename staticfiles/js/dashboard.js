// Dashboard JavaScript

// Mobile Menu Toggle
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const mobileMenu = document.getElementById('mobileMenu');

if (mobileMenuBtn && mobileMenu) {
    mobileMenuBtn.addEventListener('click', () => {
        mobileMenu.classList.toggle('active');
        mobileMenuBtn.textContent = mobileMenu.classList.contains('active') ? '✕' : '☰';
    });
}

// Copy Referral Code
const copyBtn = document.getElementById('copyBtn');
const referralCode = document.getElementById('referralCode');
const copyText = document.getElementById('copyText');
const copyIcon = document.getElementById('copyIcon');

if (copyBtn && referralCode) {
    copyBtn.addEventListener('click', () => {
        const code = referralCode.textContent;
        
        navigator.clipboard.writeText(code).then(() => {
            copyText.textContent = 'Copied!';
            copyIcon.textContent = '✓';
            copyBtn.style.background = 'linear-gradient(135deg, #22c55e, #10b981)';
            
            setTimeout(() => {
                copyText.textContent = 'Copy';
                copyIcon.textContent = '📋';
                copyBtn.style.background = 'linear-gradient(135deg, var(--purple-500), var(--pink-500))';
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
            copyText.textContent = 'Error';
            setTimeout(() => {
                copyText.textContent = 'Copy';
            }, 2000);
        });
    });
}

// Earnings Chart
const ctx = document.getElementById('earningsChart');
if (ctx) {
    const chartData = {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [{
            label: 'Daily Earnings',
            data: [85, 92, 78, 105, 125, 110, 95],
            backgroundColor: (context) => {
                const chart = context.chart;
                const {ctx, chartArea} = chart;
                if (!chartArea) return null;
                
                const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
                gradient.addColorStop(0, 'rgba(168, 85, 247, 0.8)');
                gradient.addColorStop(1, 'rgba(236, 72, 153, 0.8)');
                return gradient;
            },
            borderColor: 'rgba(168, 85, 247, 1)',
            borderWidth: 2,
            borderRadius: 8,
            tension: 0.4
        }]
    };

    const config = {
        type: 'bar',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: 'rgba(168, 85, 247, 0.5)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return '$' + context.parsed.y.toFixed(2);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.5)',
                        callback: function(value) {
                            return '$' + value;
                        }
                    }
                },
                x: {
                    grid: {
                        display: false,
                        drawBorder: false
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.5)'
                    }
                }
            },
            animation: {
                duration: 2000,
                easing: 'easeInOutQuart'
            }
        }
    };

    new Chart(ctx, config);
}

// Real-time Updates Simulation
function updateStats() {
    // Simulate real-time balance updates
    const balanceElements = document.querySelectorAll('.balance-amount');
    balanceElements.forEach(el => {
        const currentBalance = parseFloat(el.textContent.replace('$', ''));
        const newBalance = currentBalance + (Math.random() * 0.5);
        el.textContent = '$' + newBalance.toFixed(2);
    });
}

// Update stats every 30 seconds
setInterval(updateStats, 30000);

// Activity Items Click Animation
const activityItems = document.querySelectorAll('.activity-item');
activityItems.forEach(item => {
    item.addEventListener('click', function() {
        this.style.transform = 'scale(0.98)';
        setTimeout(() => {
            this.style.transform = '';
        }, 150);
    });
});

// Offer Items Click Handler
const offerItems = document.querySelectorAll('.offer-item');
offerItems.forEach(item => {
    item.addEventListener('click', function() {
        const offerType = this.querySelector('.offer-type').textContent;
        const offerAmount = this.querySelector('.offer-amount').textContent;
        
        // Add visual feedback
        this.style.transform = 'scale(0.95)';
        setTimeout(() => {
            this.style.transform = '';
        }, 150);
        
        // Show notification (you can replace this with a modal)
        showNotification(`Starting ${offerType} for ${offerAmount}`);
    });
});

// Notification System
function showNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #a855f7, #ec4899);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(168, 85, 247, 0.3);
        z-index: 1000;
        animation: slideInRight 0.3s ease-out;
        font-weight: 600;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Add notification animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(100px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    @keyframes slideOutRight {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }
`;
document.head.appendChild(style);

// Stat Cards Hover Effects
const statCards = document.querySelectorAll('.stat-card');
statCards.forEach(card => {
    card.addEventListener('mouseenter', function() {
        this.style.animation = 'pulse 0.5s ease-in-out';
    });
    
    card.addEventListener('animationend', function() {
        this.style.animation = '';
    });
});

// Initialize tooltips (if needed)
function initTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    tooltipElements.forEach(el => {
        el.addEventListener('mouseenter', function(e) {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = this.dataset.tooltip;
            tooltip.style.cssText = `
                position: absolute;
                background: rgba(15, 23, 42, 0.95);
                color: white;
                padding: 0.5rem 0.75rem;
                border-radius: 6px;
                font-size: 0.875rem;
                pointer-events: none;
                z-index: 1000;
                border: 1px solid rgba(168, 85, 247, 0.3);
            `;
            
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + 'px';
            
            this._tooltip = tooltip;
        });
        
        el.addEventListener('mouseleave', function() {
            if (this._tooltip) {
                document.body.removeChild(this._tooltip);
                this._tooltip = null;
            }
        });
    });
}

initTooltips();

// Loading Animation on Page Load
window.addEventListener('load', () => {
    const elements = document.querySelectorAll('.stat-card, .chart-section, .activity-section, .offers-section, .referral-section');
    elements.forEach((el, index) => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            el.style.transition = 'all 0.6s ease-out';
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, index * 100);
    });
});

// Console welcome message
console.log('%c🚀 EARNING PRO Dashboard', 'color: #a855f7; font-size: 24px; font-weight: bold;');
console.log('%cWelcome to your earnings dashboard!', 'color: #ec4899; font-size: 14px;');