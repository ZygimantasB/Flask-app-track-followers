/**
 * UI components and rendering for GitHub Followers Tracker
 */

import { showNotification, formatNumber, formatRelativeTime } from './utils.js';
import * as api from './api.js';

// ===== State =====

export const state = {
    currentDataType: 'followers',
    currentPage: 1,
    currentSearch: '',
    currentSort: 'username',
    currentOrder: 'asc',
    currentPreviewUsername: null
};

// ===== Tab Management =====

/**
 * Open a tab
 * @param {string} tabId - Tab ID to open
 */
export function openTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

    document.getElementById(tabId)?.classList.add('active');
    document.querySelector(`[data-tab="${tabId}"]`)?.classList.add('active');

    // Extract data type from tab id
    state.currentDataType = tabId.replace('-tab', '').replace(/-/g, '_');
}

// ===== User List Rendering =====

const DATA_MAPPINGS = {
    followers: { list: 'followers-list', count: 'followers-count', key: 'followers' },
    following: { list: 'following-list', count: 'following-count', key: 'following' },
    new_followers: { list: 'new-followers-list', count: 'new-followers-count', key: 'new_followers' },
    unfollowers: { list: 'unfollowers-list', count: 'unfollowers-count', key: 'unfollowers' },
    not_following_back: { list: 'not-following-back-list', count: 'not-following-back-count', key: 'not_following_back' },
    suggested_users: { list: 'suggested-users-list', count: 'suggested-users-count', key: 'suggested_users' },
    users_more_following: { list: 'users-more-following-list', count: 'users-more-following-count', key: 'users_more_following' }
};

/**
 * Populate data list from API response
 * @param {string} dataType - Data type
 * @param {Object} data - API response data
 */
export function populateData(dataType, data) {
    const mapping = DATA_MAPPINGS[dataType];
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
    } else {
        listElement.innerHTML = '<li class="empty-message">No users found</li>';
    }

    // Update pagination
    const paginationId = `${mapping.list.replace('-list', '')}-pagination`;
    renderPagination(paginationId, pagination, dataType);
}

/**
 * Create a user list item element
 * @param {Object} item - User data
 * @param {string} dataType - Data type for context
 * @returns {HTMLElement} List item element
 */
export function createUserListItem(item, dataType) {
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
    const avatarUrl = item.avatar_url || `https://github.com/${item.login || item}.png?size=40`;
    const avatar = document.createElement('img');
    avatar.src = avatarUrl;
    avatar.alt = item.login || item;
    avatar.className = 'user-avatar';
    avatar.loading = 'lazy';
    avatar.onclick = () => showUserPreview(item.login || item);
    li.appendChild(avatar);

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
        countsSpan.innerHTML = `
            <i class="fas fa-users"></i> ${formatNumber(item.followers)}
            <i class="fas fa-user-friends"></i> ${formatNumber(item.following)}
        `;
        userInfoDiv.appendChild(countsSpan);

        if (dataType === 'users_more_following' && item.difference !== undefined) {
            const diffSpan = document.createElement('span');
            diffSpan.className = 'difference-badge';
            diffSpan.textContent = `+${item.difference}`;
            userInfoDiv.appendChild(diffSpan);
        }
    }

    // First seen date for new followers
    if (dataType === 'new_followers' && item.first_seen_at) {
        const dateSpan = document.createElement('span');
        dateSpan.className = 'date-badge';
        dateSpan.textContent = formatRelativeTime(item.first_seen_at);
        userInfoDiv.appendChild(dateSpan);
    }

    li.appendChild(userInfoDiv);

    // Action buttons
    const buttonGroup = document.createElement('div');
    buttonGroup.className = 'button-group';

    if (['following', 'followers', 'not_following_back', 'unfollowers', 'users_more_following'].includes(dataType)) {
        const unfollowBtn = createActionButton('unfollow', item.login || item, li);
        buttonGroup.appendChild(unfollowBtn);
    }

    if (['new_followers', 'suggested_users'].includes(dataType)) {
        const followBtn = createActionButton('follow', item.login || item, li);
        buttonGroup.appendChild(followBtn);
    }

    // Ignore button
    const ignoreBtn = document.createElement('button');
    ignoreBtn.className = 'btn btn-sm btn-secondary';
    ignoreBtn.innerHTML = '<i class="fas fa-ban"></i>';
    ignoreBtn.title = 'Add to ignore list';
    ignoreBtn.onclick = () => handleAddToIgnoreList(item.login || item);
    buttonGroup.appendChild(ignoreBtn);

    if (buttonGroup.childElementCount > 0) {
        li.appendChild(buttonGroup);
    }

    return li;
}

/**
 * Create an action button (follow/unfollow)
 * @param {string} action - 'follow' or 'unfollow'
 * @param {string} username - Target username
 * @param {HTMLElement} listItem - Parent list item
 * @returns {HTMLElement} Button element
 */
function createActionButton(action, username, listItem) {
    const btn = document.createElement('button');
    btn.className = `btn btn-sm ${action === 'follow' ? 'btn-success' : 'btn-danger'}`;
    btn.innerHTML = `<i class="fas ${action === 'follow' ? 'fa-user-plus' : 'fa-user-minus'}"></i>`;
    btn.title = action === 'follow' ? 'Follow' : 'Unfollow';

    btn.onclick = async () => {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        try {
            const result = action === 'follow'
                ? await api.followUser(username)
                : await api.unfollowUser(username);

            if (result.success) {
                showNotification(`Successfully ${action}ed ${username}`, 'success');
                listItem.classList.add('fade-out');
                setTimeout(() => listItem.remove(), 500);
            } else {
                showNotification(`Failed to ${action} ${username}: ${result.message}`, 'error');
                btn.disabled = false;
                btn.innerHTML = `<i class="fas ${action === 'follow' ? 'fa-user-plus' : 'fa-user-minus'}"></i>`;
            }
        } catch (error) {
            showNotification(`Error ${action}ing ${username}`, 'error');
            btn.disabled = false;
            btn.innerHTML = `<i class="fas ${action === 'follow' ? 'fa-user-plus' : 'fa-user-minus'}"></i>`;
        }
    };

    return btn;
}

// ===== Pagination =====

/**
 * Render pagination controls
 * @param {string} containerId - Container element ID
 * @param {Object} pagination - Pagination data
 * @param {string} dataType - Data type for callbacks
 */
export function renderPagination(containerId, pagination, dataType) {
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
            btn.onclick = () => {
                state.currentPage = page;
                window.loadData(dataType, page);
            };
        }
        return btn;
    };

    // Previous button
    container.appendChild(createButton(
        pagination.page - 1,
        '<i class="fas fa-chevron-left"></i>',
        !pagination.has_prev
    ));

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
    container.appendChild(createButton(
        pagination.page + 1,
        '<i class="fas fa-chevron-right"></i>',
        !pagination.has_next
    ));
}

// ===== User Preview Modal =====

/**
 * Show user preview modal
 * @param {string} username - GitHub username
 */
export async function showUserPreview(username) {
    try {
        state.currentPreviewUsername = username;
        const data = await api.fetchUserPreview(username);

        if (data.error) {
            showNotification(data.error, 'error');
            return;
        }

        document.getElementById('preview-avatar').src = data.avatar_url;
        document.getElementById('preview-username').textContent = data.login;
        document.getElementById('preview-bio').textContent = data.bio || 'No bio available';
        document.getElementById('preview-followers').textContent = formatNumber(data.followers || 0);
        document.getElementById('preview-following').textContent = formatNumber(data.following || 0);
        document.getElementById('preview-repos').textContent = data.public_repos || 0;
        document.getElementById('preview-github-link').href = data.profile_url;

        document.getElementById('user-preview-modal').style.display = 'flex';
    } catch (error) {
        showNotification('Failed to load user preview', 'error');
    }
}

/**
 * Close user preview modal
 */
export function closeUserPreview() {
    document.getElementById('user-preview-modal').style.display = 'none';
    state.currentPreviewUsername = null;
}

/**
 * Follow user from preview modal
 */
export async function followFromPreview() {
    if (state.currentPreviewUsername) {
        try {
            const result = await api.followUser(state.currentPreviewUsername);
            if (result.success) {
                showNotification(`Successfully followed ${state.currentPreviewUsername}`, 'success');
                closeUserPreview();
            } else {
                showNotification(result.message, 'error');
            }
        } catch (error) {
            showNotification('Failed to follow user', 'error');
        }
    }
}

// ===== Simple List Rendering =====

/**
 * Render a simple list (ignore list, whitelist)
 * @param {string} listId - List element ID
 * @param {Array} items - Items to render
 * @param {string} type - List type ('ignore' or 'whitelist')
 */
export function renderSimpleList(listId, items, type) {
    const list = document.getElementById(listId);
    list.innerHTML = '';

    if (items.length === 0) {
        list.innerHTML = '<li class="empty-message">No items</li>';
        return;
    }

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
        removeBtn.onclick = () => handleRemoveFromList(type, username);
        li.appendChild(removeBtn);

        list.appendChild(li);
    });

    if (items.length > 0 && list.style.maxHeight === '0px') {
        list.style.maxHeight = '500px';
    }
}

// ===== List Management Handlers =====

/**
 * Handle adding to ignore list
 * @param {string} username - Username to add
 */
async function handleAddToIgnoreList(username) {
    try {
        const data = await api.addToIgnoreList(username);
        renderSimpleList('ignore-list', data.ignore_list || [], 'ignore');
        document.getElementById('ignore-list-count').textContent = (data.ignore_list || []).length;
        showNotification(`Added ${username} to ignore list`, 'success');
    } catch (error) {
        showNotification('Failed to add to ignore list', 'error');
    }
}

/**
 * Handle removing from list
 * @param {string} type - List type
 * @param {string} username - Username to remove
 */
async function handleRemoveFromList(type, username) {
    try {
        const data = type === 'ignore'
            ? await api.removeFromIgnoreList(username)
            : await api.removeFromWhitelist(username);

        const listKey = type === 'ignore' ? 'ignore_list' : 'whitelist';
        const listId = type === 'ignore' ? 'ignore-list' : 'whitelist';
        renderSimpleList(listId, data[listKey] || [], type);
        document.getElementById(`${listId}-count`).textContent = (data[listKey] || []).length;
        showNotification(`Removed ${username} from ${type} list`, 'success');
    } catch (error) {
        showNotification(`Failed to remove from ${type} list`, 'error');
    }
}

// ===== Dashboard Summary =====

/**
 * Update dashboard summary counts
 */
export function updateDashboardSummary() {
    const summaryIds = ['followers', 'following', 'new-followers', 'unfollowers'];
    summaryIds.forEach(id => {
        const countEl = document.getElementById(`${id}-count`);
        const summaryEl = document.getElementById(`${id}-count-summary`);
        if (countEl && summaryEl) {
            summaryEl.textContent = countEl.textContent;
        }
    });
}

// ===== Rate Limit Indicator =====

/**
 * Update rate limit display
 * @param {Object} data - Rate limit data
 */
export function updateRateLimitDisplay(data) {
    const remainingEl = document.getElementById('rate-limit-remaining');
    const totalEl = document.getElementById('rate-limit-total');
    const indicator = document.getElementById('rate-limit-indicator');

    if (remainingEl) remainingEl.textContent = data.remaining || '--';
    if (totalEl) totalEl.textContent = data.limit || '--';

    if (indicator) {
        if (data.remaining < 100) {
            indicator.classList.add('rate-limit-low');
        } else {
            indicator.classList.remove('rate-limit-low');
        }
    }
}
