/**
 * Utility functions for GitHub Followers Tracker
 */

// ===== DOM Utilities =====

/**
 * Toggle visibility of a collapsible element
 * @param {string} id - Element ID to toggle
 */
export function toggleVisibility(id) {
    const element = document.getElementById(id);
    const toggleBtn = document.querySelector(`button[onclick="toggleVisibility('${id}')"] i`);

    if (element.style.maxHeight && element.style.maxHeight !== '0px') {
        element.style.maxHeight = '0px';
        if (toggleBtn) toggleBtn.className = 'fas fa-chevron-down';
    } else {
        element.style.maxHeight = element.scrollHeight + 200 + 'px';
        if (toggleBtn) toggleBtn.className = 'fas fa-chevron-up';
    }
}

/**
 * Toggle between light and dark theme
 */
export function toggleTheme() {
    const body = document.body;
    const themeIcon = document.querySelector('#theme-toggle i');

    if (body.classList.contains('light-theme')) {
        body.classList.remove('light-theme');
        themeIcon.className = 'fas fa-moon';
        localStorage.setItem('theme', 'dark');
    } else {
        body.classList.add('light-theme');
        themeIcon.className = 'fas fa-sun';
        localStorage.setItem('theme', 'light');
    }
}

/**
 * Apply saved theme from localStorage
 */
export function applySavedTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
        const icon = document.querySelector('#theme-toggle i');
        if (icon) icon.className = 'fas fa-sun';
    }
}

// ===== Notification System =====

/**
 * Show a toast notification
 * @param {string} message - Notification message
 * @param {string} type - Notification type: 'info', 'success', 'warning', 'error'
 */
export function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;

    const iconClass = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    }[type] || 'fa-info-circle';

    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${iconClass}"></i>
            <p>${message}</p>
        </div>
        <button class="notification-close"><i class="fas fa-times"></i></button>
    `;

    document.body.appendChild(notification);

    // Close button handler
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.classList.add('notification-hide');
        setTimeout(() => notification.remove(), 300);
    });

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (document.body.contains(notification)) {
            notification.classList.add('notification-hide');
            setTimeout(() => {
                if (document.body.contains(notification)) notification.remove();
            }, 300);
        }
    }, 5000);
}

// ===== Loading Indicator =====

/**
 * Show loading indicator
 */
export function showLoading() {
    const indicator = document.getElementById('loading-indicator');
    if (indicator) indicator.style.display = 'block';
}

/**
 * Hide loading indicator
 */
export function hideLoading() {
    const indicator = document.getElementById('loading-indicator');
    if (indicator) indicator.style.display = 'none';
}

// ===== Formatting Utilities =====

/**
 * Format a number with K/M suffix
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
export function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

/**
 * Format a date string
 * @param {string} dateStr - ISO date string
 * @returns {string} Formatted date
 */
export function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Format relative time (e.g., "2 hours ago")
 * @param {string} dateStr - ISO date string
 * @returns {string} Relative time string
 */
export function formatRelativeTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    return formatDate(dateStr);
}

// ===== Debounce Utility =====

/**
 * Debounce a function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ===== URL Utilities =====

/**
 * Build URL with query parameters
 * @param {string} base - Base URL
 * @param {Object} params - Query parameters
 * @returns {string} URL with query string
 */
export function buildUrl(base, params) {
    const url = new URL(base, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            url.searchParams.set(key, value);
        }
    });
    return url.toString();
}
