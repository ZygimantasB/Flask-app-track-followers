// ===== Global State =====
let currentDataType = 'followers';
let currentPage = 1;
let currentSearch = '';
let currentSort = 'username';
let currentOrder = 'asc';
let currentPreviewUsername = null;

// ===== Utility Functions =====

function toggleVisibility(id) {
    const element = document.getElementById(id);
    const toggleBtn = document.querySelector(`button[onclick="toggleVisibility('${id}')"] i`);

    if (element.style.maxHeight && element.style.maxHeight !== '0px') {
        element.style.maxHeight = '0px';
        if (toggleBtn) toggleBtn.className = 'fas fa-chevron-down';
    } else {
        element.style.maxHeight = element.scrollHeight + 200 + "px";
        if (toggleBtn) toggleBtn.className = 'fas fa-chevron-up';
    }
}

function toggleTheme() {
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

function openTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');

    // Extract data type from tab id
    currentDataType = tabId.replace('-tab', '').replace(/-/g, '_');
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle'}"></i>
            <p>${message}</p>
        </div>
        <button class="notification-close"><i class="fas fa-times"></i></button>
    `;

    document.body.appendChild(notification);

    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.classList.add('notification-hide');
        setTimeout(() => notification.remove(), 300);
    });

    setTimeout(() => {
        if (document.body.contains(notification)) {
            notification.classList.add('notification-hide');
            setTimeout(() => {
                if (document.body.contains(notification)) notification.remove();
            }, 300);
        }
    }, 5000);
}

function showLoadingIndicator() {
    document.getElementById('loading-indicator').style.display = 'block';
}

function hideLoadingIndicator() {
    document.getElementById('loading-indicator').style.display = 'none';
}

function updateDashboardSummary() {
    const summaryIds = ['followers', 'following', 'new-followers', 'unfollowers'];
    summaryIds.forEach(id => {
        const countEl = document.getElementById(`${id}-count`);
        const summaryEl = document.getElementById(`${id}-count-summary`);
        if (countEl && summaryEl) {
            summaryEl.textContent = countEl.textContent;
        }
    });
}

// ===== Rate Limit Monitoring =====

async function updateRateLimit() {
    try {
        const response = await fetch('/api/rate-limit');
        const data = await response.json();
        document.getElementById('rate-limit-remaining').textContent = data.remaining || '--';
        document.getElementById('rate-limit-total').textContent = data.limit || '--';

        const indicator = document.getElementById('rate-limit-indicator');
        if (data.remaining < 100) {
            indicator.classList.add('rate-limit-low');
        } else {
            indicator.classList.remove('rate-limit-low');
        }
    } catch (error) {
        console.error('Failed to fetch rate limit:', error);
    }
}

// ===== Data Fetching =====

async function fetchData(dataType, page = 1) {
    try {
        showLoadingIndicator();
        currentDataType = dataType;
        currentPage = page;

        const params = new URLSearchParams({
            type: dataType,
            page: page,
            per_page: 50,
            search: currentSearch,
            sort: currentSort,
            order: currentOrder
        });

        const response = await fetch(`/get_data?${params}`);
        if (!response.ok) throw new Error(`Server responded with status: ${response.status}`);

        const data = await response.json();
        if (data.error) {
            showNotification(data.error, 'error');
            return;
        }

        populateData(dataType, data);
        updateDashboardSummary();
        updateRateLimit();
        showNotification(`${dataType.replace(/_/g, ' ')} loaded successfully`, 'success');
    } catch (error) {
        console.error('Error fetching data:', error);
        showNotification(`Failed to load data: ${error.message}`, 'error');
    } finally {
        hideLoadingIndicator();
    }
}

function populateData(dataType, data) {
    const mappings = {
        'followers': { list: 'followers-list', count: 'followers-count', key: 'followers' },
        'following': { list: 'following-list', count: 'following-count', key: 'following' },
        'new_followers': { list: 'new-followers-list', count: 'new-followers-count', key: 'new_followers' },
        'unfollowers': { list: 'unfollowers-list', count: 'unfollowers-count', key: 'unfollowers' },
        'not_following_back': { list: 'not-following-back-list', count: 'not-following-back-count', key: 'not_following_back' },
        'suggested_users': { list: 'suggested-users-list', count: 'suggested-users-count', key: 'suggested_users' },
        'users_more_following': { list: 'users-more-following-list', count: 'users-more-following-count', key: 'users_more_following' }
    };

    const mapping = mappings[dataType];
    if (!mapping) return;

    const listElement = document.getElementById(mapping.list);
    const countElement = document.getElementById(mapping.count);
    const dataList = data[mapping.key] || [];
    const pagination = data.pagination;

    // Update count
    if (countElement) {
        countElement.textContent = data.total_count || dataList.length;
        const summaryEl = document.getElementById(`${mapping.count}-summary`);
        if (summaryEl) summaryEl.textContent = data.total_count || dataList.length;
    }

    // Clear and populate list
    listElement.innerHTML = '';

    if (dataList.length > 0) {
        // Ensure list is visible
        if (!listElement.style.maxHeight || listElement.style.maxHeight === '0px') {
            listElement.style.maxHeight = '2000px';
        }

        dataList.forEach(item => {
            const li = createUserListItem(item, dataType);
            listElement.appendChild(li);
        });

        addFormEventListeners();
    }

    // Update pagination
    const paginationId = `${mapping.list.replace('-list', '')}-pagination`;
    renderPagination(paginationId, pagination, dataType);
}

function createUserListItem(item, dataType) {
    const li = document.createElement('li');
    li.className = 'list-item';
    li.dataset.username = item.login || item;

    // Checkbox for suggested users
    if (dataType === 'suggested_users') {
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.dataset.username = item.login || item;
        checkbox.className = 'user-checkbox';
        li.appendChild(checkbox);
    }

    // Avatar
    if (item.avatar_url) {
        const avatar = document.createElement('img');
        avatar.src = item.avatar_url;
        avatar.alt = item.login;
        avatar.className = 'user-avatar';
        avatar.onclick = () => showUserPreview(item.login);
        li.appendChild(avatar);
    }

    // User info
    const userInfoDiv = document.createElement('div');
    userInfoDiv.className = 'user-info';

    const usernameSpan = document.createElement('span');
    usernameSpan.className = 'username';
    usernameSpan.textContent = item.login || item;
    usernameSpan.onclick = () => showUserPreview(item.login || item);
    userInfoDiv.appendChild(usernameSpan);

    // Stats
    if (item.followers !== undefined && item.following !== undefined) {
        const countsSpan = document.createElement('span');
        countsSpan.className = 'counts';
        countsSpan.innerHTML = `<i class="fas fa-users"></i> ${item.followers} <i class="fas fa-user-friends"></i> ${item.following}`;
        userInfoDiv.appendChild(countsSpan);

        if (dataType === 'users_more_following' && item.difference !== undefined) {
            const diffSpan = document.createElement('span');
            diffSpan.className = 'difference-badge';
            diffSpan.textContent = `+${item.difference}`;
            userInfoDiv.appendChild(diffSpan);
        }
    }

    li.appendChild(userInfoDiv);

    // Action buttons
    const buttonGroup = document.createElement('div');
    buttonGroup.className = 'button-group';

    if (['following', 'followers', 'not_following_back', 'unfollowers', 'users_more_following'].includes(dataType)) {
        const unfollowBtn = document.createElement('button');
        unfollowBtn.className = 'btn btn-sm btn-danger';
        unfollowBtn.innerHTML = '<i class="fas fa-user-minus"></i>';
        unfollowBtn.title = 'Unfollow';
        unfollowBtn.onclick = () => unfollowUser(item.login || item, li);
        buttonGroup.appendChild(unfollowBtn);
    }

    if (['new_followers', 'suggested_users'].includes(dataType)) {
        const followBtn = document.createElement('button');
        followBtn.className = 'btn btn-sm btn-success';
        followBtn.innerHTML = '<i class="fas fa-user-plus"></i>';
        followBtn.title = 'Follow';
        followBtn.onclick = () => followUser(item.login || item, li);
        buttonGroup.appendChild(followBtn);
    }

    // Add to ignore/whitelist buttons
    const ignoreBtn = document.createElement('button');
    ignoreBtn.className = 'btn btn-sm btn-secondary';
    ignoreBtn.innerHTML = '<i class="fas fa-ban"></i>';
    ignoreBtn.title = 'Add to ignore list';
    ignoreBtn.onclick = () => addToIgnoreList(item.login || item);
    buttonGroup.appendChild(ignoreBtn);

    if (buttonGroup.childElementCount > 0) {
        li.appendChild(buttonGroup);
    }

    return li;
}

function renderPagination(containerId, pagination, dataType) {
    const container = document.getElementById(containerId);
    if (!container || !pagination) return;

    container.innerHTML = '';

    if (pagination.total_pages <= 1) return;

    const createButton = (page, text, disabled = false, active = false) => {
        const btn = document.createElement('button');
        btn.className = `pagination-btn ${active ? 'active' : ''} ${disabled ? 'disabled' : ''}`;
        btn.innerHTML = text;
        btn.disabled = disabled;
        if (!disabled && !active) {
            btn.onclick = () => fetchData(dataType, page);
        }
        return btn;
    };

    // Previous button
    container.appendChild(createButton(pagination.page - 1, '<i class="fas fa-chevron-left"></i>', !pagination.has_prev));

    // Page numbers
    const maxVisible = 5;
    let startPage = Math.max(1, pagination.page - Math.floor(maxVisible / 2));
    let endPage = Math.min(pagination.total_pages, startPage + maxVisible - 1);

    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) {
        container.appendChild(createButton(1, '1'));
        if (startPage > 2) {
            const dots = document.createElement('span');
            dots.className = 'pagination-dots';
            dots.textContent = '...';
            container.appendChild(dots);
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        container.appendChild(createButton(i, i.toString(), false, i === pagination.page));
    }

    if (endPage < pagination.total_pages) {
        if (endPage < pagination.total_pages - 1) {
            const dots = document.createElement('span');
            dots.className = 'pagination-dots';
            dots.textContent = '...';
            container.appendChild(dots);
        }
        container.appendChild(createButton(pagination.total_pages, pagination.total_pages.toString()));
    }

    // Next button
    container.appendChild(createButton(pagination.page + 1, '<i class="fas fa-chevron-right"></i>', !pagination.has_next));
}

// ===== User Actions =====

async function followUser(username, listItem = null) {
    try {
        const response = await fetch(`/follow/${username}`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showNotification(`Successfully followed ${username}`, 'success');
            if (listItem) {
                listItem.classList.add('fade-out');
                setTimeout(() => listItem.remove(), 500);
            }
        } else {
            showNotification(`Failed to follow ${username}: ${data.message}`, 'error');
        }
    } catch (error) {
        showNotification(`Error following ${username}`, 'error');
    }
}

async function unfollowUser(username, listItem = null) {
    try {
        const response = await fetch(`/unfollow/${username}`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showNotification(`Successfully unfollowed ${username}`, 'success');
            if (listItem) {
                listItem.classList.add('fade-out');
                setTimeout(() => listItem.remove(), 500);
            }
        } else {
            showNotification(`Failed to unfollow ${username}: ${data.message}`, 'error');
        }
    } catch (error) {
        showNotification(`Error unfollowing ${username}`, 'error');
    }
}

async function bulkAction(listId, endpoint) {
    // Map list IDs to data types for fetching all usernames
    const listToDataType = {
        'followers-list': 'followers',
        'following-list': 'following',
        'new-followers-list': 'new_followers',
        'unfollowers-list': 'unfollowers',
        'not-following-back-list': 'not_following_back',
        'suggested-users-list': 'suggested_users'
    };

    const dataType = listToDataType[listId];
    if (!dataType) {
        showNotification('Unknown list type', 'error');
        return;
    }

    try {
        showLoadingIndicator();

        // Fetch ALL usernames from the server (not just the current page)
        const allUsersResponse = await fetch(`/get_all_usernames?type=${dataType}`);
        const allUsersData = await allUsersResponse.json();

        if (allUsersData.error) {
            showNotification(allUsersData.error, 'error');
            return;
        }

        const usernames = allUsersData.usernames || [];

        if (usernames.length === 0) {
            showNotification('No users to process', 'info');
            return;
        }

        hideLoadingIndicator();

        if (!confirm(`Are you sure you want to process ALL ${usernames.length} users? This may take a while.`)) return;

        showLoadingIndicator();

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usernames })
        });

        const results = await response.json();
        let successCount = 0, failCount = 0;

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

        updateDashboardSummary();
        updateRateLimit();

        if (successCount > 0 && failCount === 0) {
            showNotification(`Successfully processed ${successCount} users`, 'success');
        } else if (successCount > 0) {
            showNotification(`Processed ${successCount} users, failed for ${failCount}`, 'warning');
        } else {
            showNotification('Failed to process any users', 'error');
        }

        // Refresh the list after bulk operation
        if (successCount > 0) {
            setTimeout(() => fetchData(dataType, 1), 1000);
        }
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        hideLoadingIndicator();
    }
}

async function followSelectedUsers() {
    const list = document.getElementById('suggested-users-list');
    const selectedCheckboxes = list.querySelectorAll('.user-checkbox:checked');
    const usernames = Array.from(selectedCheckboxes).map(cb => cb.dataset.username);

    if (usernames.length === 0) {
        showNotification('No users selected', 'info');
        return;
    }

    try {
        showLoadingIndicator();
        const response = await fetch('/bulk_follow', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usernames })
        });

        const results = await response.json();
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

        showNotification(`Successfully followed ${successCount} users`, 'success');
        updateRateLimit();
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        hideLoadingIndicator();
    }
}

// ===== User Preview Modal =====

async function showUserPreview(username) {
    try {
        currentPreviewUsername = username;
        const response = await fetch(`/api/user/${username}/preview`);
        const data = await response.json();

        if (data.error) {
            showNotification(data.error, 'error');
            return;
        }

        document.getElementById('preview-avatar').src = data.avatar_url;
        document.getElementById('preview-username').textContent = data.login;
        document.getElementById('preview-bio').textContent = data.bio || 'No bio available';
        document.getElementById('preview-followers').textContent = data.followers || 0;
        document.getElementById('preview-following').textContent = data.following || 0;
        document.getElementById('preview-repos').textContent = data.public_repos || 0;
        document.getElementById('preview-github-link').href = data.profile_url;

        document.getElementById('user-preview-modal').style.display = 'flex';
    } catch (error) {
        showNotification('Failed to load user preview', 'error');
    }
}

function closeUserPreview() {
    document.getElementById('user-preview-modal').style.display = 'none';
    currentPreviewUsername = null;
}

async function followFromPreview() {
    if (currentPreviewUsername) {
        await followUser(currentPreviewUsername);
        closeUserPreview();
    }
}

// ===== Ignore List & Whitelist =====

async function fetchIgnoreList() {
    try {
        const response = await fetch('/api/ignore-list');
        const data = await response.json();
        renderSimpleList('ignore-list', data.ignore_list || [], 'ignore');
        document.getElementById('ignore-list-count').textContent = (data.ignore_list || []).length;
    } catch (error) {
        console.error('Failed to fetch ignore list:', error);
    }
}

async function fetchWhitelist() {
    try {
        const response = await fetch('/api/whitelist');
        const data = await response.json();
        renderSimpleList('whitelist', data.whitelist || [], 'whitelist');
        document.getElementById('whitelist-count').textContent = (data.whitelist || []).length;
    } catch (error) {
        console.error('Failed to fetch whitelist:', error);
    }
}

function renderSimpleList(listId, items, type) {
    const list = document.getElementById(listId);
    list.innerHTML = '';

    items.forEach(username => {
        const li = document.createElement('li');
        li.className = 'list-item mini-item';
        li.dataset.username = username;

        const span = document.createElement('span');
        span.className = 'username';
        span.textContent = username;
        li.appendChild(span);

        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn btn-sm btn-danger';
        removeBtn.innerHTML = '<i class="fas fa-times"></i>';
        removeBtn.onclick = () => removeFromList(type, username);
        li.appendChild(removeBtn);

        list.appendChild(li);
    });

    if (items.length > 0 && list.style.maxHeight === '0px') {
        list.style.maxHeight = '500px';
    }
}

async function addToIgnoreList(username) {
    try {
        const response = await fetch('/api/ignore-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await response.json();
        renderSimpleList('ignore-list', data.ignore_list || [], 'ignore');
        document.getElementById('ignore-list-count').textContent = (data.ignore_list || []).length;
        showNotification(`Added ${username} to ignore list`, 'success');
    } catch (error) {
        showNotification('Failed to add to ignore list', 'error');
    }
}

async function addToWhitelist(username) {
    try {
        const response = await fetch('/api/whitelist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await response.json();
        renderSimpleList('whitelist', data.whitelist || [], 'whitelist');
        document.getElementById('whitelist-count').textContent = (data.whitelist || []).length;
        showNotification(`Added ${username} to whitelist`, 'success');
    } catch (error) {
        showNotification('Failed to add to whitelist', 'error');
    }
}

async function removeFromList(type, username) {
    const endpoint = type === 'ignore' ? '/api/ignore-list' : '/api/whitelist';
    try {
        const response = await fetch(endpoint, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await response.json();
        const listKey = type === 'ignore' ? 'ignore_list' : 'whitelist';
        const listId = type === 'ignore' ? 'ignore-list' : 'whitelist';
        renderSimpleList(listId, data[listKey] || [], type);
        document.getElementById(`${listId}-count`).textContent = (data[listKey] || []).length;
        showNotification(`Removed ${username} from ${type} list`, 'success');
    } catch (error) {
        showNotification(`Failed to remove from ${type} list`, 'error');
    }
}

// ===== Analytics =====

async function loadAnalytics() {
    try {
        const days = document.getElementById('analytics-period').value;
        const response = await fetch(`/api/analytics?days=${days}`);
        const data = await response.json();

        document.getElementById('analytics-growth').textContent =
            (data.summary.total_growth >= 0 ? '+' : '') + data.summary.total_growth;
        document.getElementById('analytics-rate').textContent = data.summary.growth_rate_percent + '%';
        document.getElementById('analytics-gained').textContent = data.summary.total_gained;
        document.getElementById('analytics-lost').textContent = data.summary.total_lost;

        // Simple chart visualization
        const chartContainer = document.getElementById('analytics-chart');
        if (data.snapshots && data.snapshots.length > 0) {
            renderSimpleChart(chartContainer, data.snapshots);
        }

        // Expand analytics section
        const content = document.getElementById('analytics-content');
        if (content.style.maxHeight === '0px') {
            content.style.maxHeight = '500px';
        }
    } catch (error) {
        showNotification('Failed to load analytics', 'error');
    }
}

function renderSimpleChart(container, snapshots) {
    container.innerHTML = '';

    if (snapshots.length === 0) {
        container.innerHTML = '<p class="chart-placeholder">No data available</p>';
        return;
    }

    const maxFollowers = Math.max(...snapshots.map(s => s.followers));
    const minFollowers = Math.min(...snapshots.map(s => s.followers));
    const range = maxFollowers - minFollowers || 1;

    const chartDiv = document.createElement('div');
    chartDiv.className = 'simple-chart';

    snapshots.forEach((snapshot, index) => {
        const bar = document.createElement('div');
        bar.className = 'chart-bar';
        const height = ((snapshot.followers - minFollowers) / range) * 100;
        bar.style.height = `${Math.max(5, height)}%`;
        bar.title = `${snapshot.date.split('T')[0]}: ${snapshot.followers} followers`;

        if (index === snapshots.length - 1) {
            bar.classList.add('chart-bar-latest');
        }

        chartDiv.appendChild(bar);
    });

    container.appendChild(chartDiv);
}

// ===== Export =====

function exportData() {
    const type = document.getElementById('export-type').value;
    const format = document.getElementById('export-format').value;
    window.open(`/api/export?type=${type}&format=${format}&days=30`, '_blank');
}

// ===== Search User =====

async function searchUser(username) {
    try {
        const response = await fetch(`/check_follow?username=${encodeURIComponent(username)}`);
        const data = await response.json();
        const resultDiv = document.getElementById('search-result');

        if (data.error) {
            resultDiv.innerHTML = `<span class="error">${data.error}</span>`;
        } else {
            const followsYou = data.follows_you;
            resultDiv.innerHTML = `
                <strong>${data.username}</strong> ${followsYou ? '<span class="success">follows you</span>' : '<span class="warning">does not follow you</span>'}
                <button class="btn btn-sm btn-primary" onclick="showUserPreview('${data.username}')">
                    <i class="fas fa-eye"></i> Preview
                </button>
            `;
        }
    } catch (error) {
        console.error('Error searching user:', error);
        showNotification('Failed to search user', 'error');
    }
}

// ===== Form Event Listeners =====

function addFormEventListeners() {
    // Re-bind form listeners after dynamic content update
    document.querySelectorAll('.unfollow-form').forEach(form => {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            const username = this.action.split('/').pop();
            await unfollowUser(username, this.closest('.list-item'));
        });
    });

    document.querySelectorAll('.follow-form').forEach(form => {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            const username = this.action.split('/').pop();
            await followUser(username, this.closest('.list-item'));
        });
    });
}

// ===== Initialization =====

document.addEventListener('DOMContentLoaded', function() {
    // Apply saved theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
        document.querySelector('#theme-toggle i').className = 'fas fa-sun';
    }

    // Theme toggle
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

    // Tab navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            openTab(this.getAttribute('data-tab'));
        });
    });

    // Load data buttons
    document.querySelectorAll('.load-data-button').forEach(button => {
        button.addEventListener('click', function() {
            fetchData(this.getAttribute('data-type'));
        });
    });

    // Bulk action buttons
    document.getElementById('follow-all-new-followers-button').addEventListener('click', () => bulkAction('new-followers-list', '/bulk_follow'));
    document.getElementById('unfollow-all-followers-button').addEventListener('click', () => bulkAction('followers-list', '/bulk_unfollow'));
    document.getElementById('unfollow-all-following-button').addEventListener('click', () => bulkAction('following-list', '/bulk_unfollow'));
    document.getElementById('unfollow-all-unfollowers-button').addEventListener('click', () => bulkAction('unfollowers-list', '/bulk_unfollow'));
    document.getElementById('unfollow-all-not-following-back-button').addEventListener('click', () => bulkAction('not-following-back-list', '/bulk_unfollow'));
    document.getElementById('follow-selected-suggested-users-button').addEventListener('click', followSelectedUsers);
    document.getElementById('follow-all-suggested-users-button').addEventListener('click', () => bulkAction('suggested-users-list', '/bulk_follow'));

    // Search form
    document.getElementById('search-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const username = document.getElementById('search-username').value.trim();
        if (username) searchUser(username);
    });

    // Ignore list form
    document.getElementById('ignore-list-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const input = document.getElementById('ignore-username-input');
        const username = input.value.trim();
        if (username) {
            await addToIgnoreList(username);
            input.value = '';
        }
    });

    // Whitelist form
    document.getElementById('whitelist-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const input = document.getElementById('whitelist-username-input');
        const username = input.value.trim();
        if (username) {
            await addToWhitelist(username);
            input.value = '';
        }
    });

    // Refresh buttons
    document.getElementById('refresh-ignore-list').addEventListener('click', fetchIgnoreList);
    document.getElementById('refresh-whitelist').addEventListener('click', fetchWhitelist);

    // Analytics
    document.getElementById('load-analytics').addEventListener('click', loadAnalytics);

    // Export
    document.getElementById('export-btn').addEventListener('click', exportData);

    // Search and sort controls
    let searchTimeout;
    document.getElementById('list-search').addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentSearch = this.value.trim();
            if (currentDataType) {
                fetchData(currentDataType, 1);
            }
        }, 300);
    });

    document.getElementById('sort-by').addEventListener('change', function() {
        currentSort = this.value;
        if (currentDataType) {
            fetchData(currentDataType, 1);
        }
    });

    document.getElementById('sort-order').addEventListener('click', function() {
        currentOrder = currentOrder === 'asc' ? 'desc' : 'asc';
        const icon = this.querySelector('i');
        icon.className = currentOrder === 'asc' ? 'fas fa-sort-amount-down' : 'fas fa-sort-amount-up';
        if (currentDataType) {
            fetchData(currentDataType, 1);
        }
    });

    // Close modal when clicking outside
    document.getElementById('user-preview-modal').addEventListener('click', function(e) {
        if (e.target === this) closeUserPreview();
    });

    // Initial data load
    fetchIgnoreList();
    fetchWhitelist();
    updateRateLimit();

    // Update rate limit periodically
    setInterval(updateRateLimit, 60000);
});
