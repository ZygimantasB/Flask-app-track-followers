/**
 * Main entry point for GitHub Followers Tracker
 * Initializes all modules and sets up event listeners
 */

import * as utils from './utils.js';
import * as api from './api.js';
import * as ui from './ui.js';
import * as charts from './charts.js';

// ===== Global State Exposure =====
// Export loadData to window for pagination callbacks
window.loadData = loadData;

// ===== Main Data Loading =====

/**
 * Load data for a specific type
 * @param {string} dataType - Data type to load
 * @param {number} page - Page number
 */
async function loadData(dataType, page = 1) {
    try {
        utils.showLoading();
        ui.state.currentDataType = dataType;
        ui.state.currentPage = page;

        const data = await api.fetchData(dataType, {
            page,
            perPage: 50,
            search: ui.state.currentSearch,
            sort: ui.state.currentSort,
            order: ui.state.currentOrder
        });

        if (data.error) {
            utils.showNotification(data.error, 'error');
            return;
        }

        ui.populateData(dataType, data);
        ui.updateDashboardSummary();
        updateRateLimit();
        utils.showNotification(`${dataType.replace(/_/g, ' ')} loaded successfully`, 'success');
    } catch (error) {
        console.error('Error fetching data:', error);
        utils.showNotification(`Failed to load data: ${error.message}`, 'error');
    } finally {
        utils.hideLoading();
    }
}

// ===== Bulk Operations =====

const LIST_TO_DATA_TYPE = {
    'followers-list': 'followers',
    'following-list': 'following',
    'new-followers-list': 'new_followers',
    'unfollowers-list': 'unfollowers',
    'not-following-back-list': 'not_following_back',
    'suggested-users-list': 'suggested_users'
};

/**
 * Perform bulk action on all users in a list
 * @param {string} listId - List element ID
 * @param {string} action - 'follow' or 'unfollow'
 */
async function bulkAction(listId, action) {
    const dataType = LIST_TO_DATA_TYPE[listId];
    if (!dataType) {
        utils.showNotification('Unknown list type', 'error');
        return;
    }

    try {
        utils.showLoading();

        // Fetch all usernames
        const allUsersData = await api.fetchAllUsernames(dataType);
        if (allUsersData.error) {
            utils.showNotification(allUsersData.error, 'error');
            return;
        }

        const usernames = allUsersData.usernames || [];
        if (usernames.length === 0) {
            utils.showNotification('No users to process', 'info');
            return;
        }

        utils.hideLoading();

        if (!confirm(`Are you sure you want to ${action} ALL ${usernames.length} users? This may take a while.`)) {
            return;
        }

        utils.showLoading();

        const results = action === 'follow'
            ? await api.bulkFollow(usernames)
            : await api.bulkUnfollow(usernames);

        let successCount = 0;
        let failCount = 0;
        const list = document.getElementById(listId);

        usernames.forEach(username => {
            if (results[username]?.success) {
                const li = list.querySelector(`.list-item[data-username="${username}"]`);
                if (li) {
                    li.classList.add('fade-out');
                    setTimeout(() => li.remove(), 500);
                }
                successCount++;
            } else {
                failCount++;
            }
        });

        ui.updateDashboardSummary();
        updateRateLimit();

        if (successCount > 0 && failCount === 0) {
            utils.showNotification(`Successfully ${action}ed ${successCount} users`, 'success');
        } else if (successCount > 0) {
            utils.showNotification(`${action}ed ${successCount} users, failed for ${failCount}`, 'warning');
        } else {
            utils.showNotification(`Failed to ${action} any users`, 'error');
        }

        // Refresh list after bulk operation
        if (successCount > 0) {
            setTimeout(() => loadData(dataType, 1), 1000);
        }
    } catch (error) {
        utils.showNotification(`Error: ${error.message}`, 'error');
    } finally {
        utils.hideLoading();
    }
}

/**
 * Follow selected users from suggested list
 */
async function followSelectedUsers() {
    const list = document.getElementById('suggested-users-list');
    const selectedCheckboxes = list.querySelectorAll('.user-checkbox:checked');
    const usernames = Array.from(selectedCheckboxes).map(cb => cb.dataset.username);

    if (usernames.length === 0) {
        utils.showNotification('No users selected', 'info');
        return;
    }

    try {
        utils.showLoading();
        const results = await api.bulkFollow(usernames);
        let successCount = 0;

        usernames.forEach(username => {
            if (results[username]?.success) {
                const li = list.querySelector(`.list-item[data-username="${username}"]`);
                if (li) {
                    li.classList.add('fade-out');
                    setTimeout(() => li.remove(), 500);
                }
                successCount++;
            }
        });

        utils.showNotification(`Successfully followed ${successCount} users`, 'success');
        updateRateLimit();
    } catch (error) {
        utils.showNotification(`Error: ${error.message}`, 'error');
    } finally {
        utils.hideLoading();
    }
}

// ===== Analytics =====

/**
 * Load and display analytics
 */
async function loadAnalytics() {
    try {
        const days = document.getElementById('analytics-period')?.value || 30;
        const data = await api.getAnalytics(days);

        // Update summary stats
        const growthEl = document.getElementById('analytics-growth');
        const rateEl = document.getElementById('analytics-rate');
        const gainedEl = document.getElementById('analytics-gained');
        const lostEl = document.getElementById('analytics-lost');

        if (growthEl) {
            const growth = data.summary.total_growth;
            growthEl.textContent = (growth >= 0 ? '+' : '') + growth;
            growthEl.className = growth >= 0 ? 'stat-positive' : 'stat-negative';
        }
        if (rateEl) rateEl.textContent = data.summary.growth_rate_percent + '%';
        if (gainedEl) gainedEl.textContent = data.summary.total_gained;
        if (lostEl) lostEl.textContent = data.summary.total_lost;

        // Render charts
        await charts.initCharts();

        const followerCanvas = document.getElementById('follower-chart');
        const activityCanvas = document.getElementById('activity-chart');

        if (followerCanvas && data.snapshots) {
            charts.renderFollowerChart(followerCanvas, data.snapshots);
        }

        if (activityCanvas && data.snapshots) {
            charts.renderActivityChart(activityCanvas, data.snapshots);
        }

        // Fallback simple chart
        const simpleChartContainer = document.getElementById('analytics-chart');
        if (simpleChartContainer && !followerCanvas) {
            charts.renderSimpleChart(simpleChartContainer, data.snapshots);
        }

        // Expand analytics section
        const content = document.getElementById('analytics-content');
        if (content && content.style.maxHeight === '0px') {
            content.style.maxHeight = '800px';
        }
    } catch (error) {
        utils.showNotification('Failed to load analytics', 'error');
    }
}

// ===== Search =====

/**
 * Search for a user
 * @param {string} username - Username to search
 */
async function searchUser(username) {
    try {
        const data = await api.checkFollow(username);
        const resultDiv = document.getElementById('search-result');

        if (data.error) {
            resultDiv.innerHTML = `<span class="error">${data.error}</span>`;
        } else {
            const followsYou = data.follows_you;
            resultDiv.innerHTML = `
                <strong>${data.username}</strong>
                ${followsYou
                    ? '<span class="success">follows you</span>'
                    : '<span class="warning">does not follow you</span>'}
                <button class="btn btn-sm btn-primary" onclick="window.showUserPreview('${data.username}')">
                    <i class="fas fa-eye"></i> Preview
                </button>
            `;
        }
    } catch (error) {
        utils.showNotification('Failed to search user', 'error');
    }
}

// ===== Rate Limit =====

/**
 * Update rate limit display
 */
async function updateRateLimit() {
    try {
        const data = await api.getRateLimit();
        ui.updateRateLimitDisplay(data);
    } catch (error) {
        console.error('Failed to fetch rate limit:', error);
    }
}

// ===== Ignore List & Whitelist =====

/**
 * Fetch and render ignore list
 */
async function fetchIgnoreList() {
    try {
        const data = await api.getIgnoreList();
        ui.renderSimpleList('ignore-list', data.ignore_list || [], 'ignore');
        document.getElementById('ignore-list-count').textContent = (data.ignore_list || []).length;
    } catch (error) {
        console.error('Failed to fetch ignore list:', error);
    }
}

/**
 * Fetch and render whitelist
 */
async function fetchWhitelist() {
    try {
        const data = await api.getWhitelist();
        ui.renderSimpleList('whitelist', data.whitelist || [], 'whitelist');
        document.getElementById('whitelist-count').textContent = (data.whitelist || []).length;
    } catch (error) {
        console.error('Failed to fetch whitelist:', error);
    }
}

// ===== Export =====

/**
 * Export data
 */
function exportData() {
    const type = document.getElementById('export-type')?.value || 'followers';
    const format = document.getElementById('export-format')?.value || 'json';
    window.open(`/api/export?type=${type}&format=${format}&days=30`, '_blank');
}

// ===== Expose Functions to Window =====

window.showUserPreview = ui.showUserPreview;
window.closeUserPreview = ui.closeUserPreview;
window.followFromPreview = ui.followFromPreview;
window.toggleVisibility = utils.toggleVisibility;

// ===== Initialization =====

document.addEventListener('DOMContentLoaded', function() {
    // Apply saved theme
    utils.applySavedTheme();

    // Theme toggle
    document.getElementById('theme-toggle')?.addEventListener('click', () => {
        utils.toggleTheme();
        charts.updateChartTheme();
    });

    // Tab navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            ui.openTab(this.getAttribute('data-tab'));
        });
    });

    // Load data buttons
    document.querySelectorAll('.load-data-button').forEach(button => {
        button.addEventListener('click', function() {
            loadData(this.getAttribute('data-type'));
        });
    });

    // Bulk action buttons
    const bulkButtons = {
        'follow-all-new-followers-button': ['new-followers-list', 'follow'],
        'unfollow-all-followers-button': ['followers-list', 'unfollow'],
        'unfollow-all-following-button': ['following-list', 'unfollow'],
        'unfollow-all-unfollowers-button': ['unfollowers-list', 'unfollow'],
        'unfollow-all-not-following-back-button': ['not-following-back-list', 'unfollow'],
        'follow-all-suggested-users-button': ['suggested-users-list', 'follow']
    };

    Object.entries(bulkButtons).forEach(([btnId, [listId, action]]) => {
        document.getElementById(btnId)?.addEventListener('click', () => bulkAction(listId, action));
    });

    document.getElementById('follow-selected-suggested-users-button')?.addEventListener('click', followSelectedUsers);

    // Search form
    document.getElementById('search-form')?.addEventListener('submit', function(e) {
        e.preventDefault();
        const username = document.getElementById('search-username')?.value.trim();
        if (username) searchUser(username);
    });

    // Ignore list form
    document.getElementById('ignore-list-form')?.addEventListener('submit', async function(e) {
        e.preventDefault();
        const input = document.getElementById('ignore-username-input');
        const username = input?.value.trim();
        if (username) {
            try {
                const data = await api.addToIgnoreList(username);
                ui.renderSimpleList('ignore-list', data.ignore_list || [], 'ignore');
                document.getElementById('ignore-list-count').textContent = (data.ignore_list || []).length;
                utils.showNotification(`Added ${username} to ignore list`, 'success');
                input.value = '';
            } catch (error) {
                utils.showNotification('Failed to add to ignore list', 'error');
            }
        }
    });

    // Whitelist form
    document.getElementById('whitelist-form')?.addEventListener('submit', async function(e) {
        e.preventDefault();
        const input = document.getElementById('whitelist-username-input');
        const username = input?.value.trim();
        if (username) {
            try {
                const data = await api.addToWhitelist(username);
                ui.renderSimpleList('whitelist', data.whitelist || [], 'whitelist');
                document.getElementById('whitelist-count').textContent = (data.whitelist || []).length;
                utils.showNotification(`Added ${username} to whitelist`, 'success');
                input.value = '';
            } catch (error) {
                utils.showNotification('Failed to add to whitelist', 'error');
            }
        }
    });

    // Refresh buttons
    document.getElementById('refresh-ignore-list')?.addEventListener('click', fetchIgnoreList);
    document.getElementById('refresh-whitelist')?.addEventListener('click', fetchWhitelist);

    // Analytics
    document.getElementById('load-analytics')?.addEventListener('click', loadAnalytics);
    document.getElementById('analytics-period')?.addEventListener('change', loadAnalytics);

    // Export
    document.getElementById('export-btn')?.addEventListener('click', exportData);

    // Search and sort controls
    const searchInput = document.getElementById('list-search');
    if (searchInput) {
        const debouncedSearch = utils.debounce((value) => {
            ui.state.currentSearch = value;
            if (ui.state.currentDataType) {
                loadData(ui.state.currentDataType, 1);
            }
        }, 300);

        searchInput.addEventListener('input', function() {
            debouncedSearch(this.value.trim());
        });
    }

    document.getElementById('sort-by')?.addEventListener('change', function() {
        ui.state.currentSort = this.value;
        if (ui.state.currentDataType) {
            loadData(ui.state.currentDataType, 1);
        }
    });

    document.getElementById('sort-order')?.addEventListener('click', function() {
        ui.state.currentOrder = ui.state.currentOrder === 'asc' ? 'desc' : 'asc';
        const icon = this.querySelector('i');
        if (icon) {
            icon.className = ui.state.currentOrder === 'asc'
                ? 'fas fa-sort-amount-down'
                : 'fas fa-sort-amount-up';
        }
        if (ui.state.currentDataType) {
            loadData(ui.state.currentDataType, 1);
        }
    });

    // Close modal when clicking outside
    document.getElementById('user-preview-modal')?.addEventListener('click', function(e) {
        if (e.target === this) ui.closeUserPreview();
    });

    // Initial data load
    fetchIgnoreList();
    fetchWhitelist();
    updateRateLimit();

    // Update rate limit periodically
    setInterval(updateRateLimit, 60000);

    console.log('GitHub Followers Tracker initialized');
});
