/**
 * API client for GitHub Followers Tracker
 */

import { showNotification, showLoading, hideLoading } from './utils.js';

const API_BASE = '';

/**
 * Make an API request with error handling
 * @param {string} endpoint - API endpoint
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} Response data
 */
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }

        return data;
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

// ===== Data Fetching =====

/**
 * Fetch data for a specific type with pagination
 * @param {string} type - Data type (followers, following, etc.)
 * @param {Object} params - Query parameters
 * @returns {Promise<Object>} Data response
 */
export async function fetchData(type, params = {}) {
    const queryParams = new URLSearchParams({
        type,
        page: params.page || 1,
        per_page: params.perPage || 50,
        search: params.search || '',
        sort: params.sort || 'username',
        order: params.order || 'asc',
        refresh: params.refresh || 'false'
    });

    return apiRequest(`/get_data?${queryParams}`);
}

/**
 * Fetch all usernames for a data type (no pagination)
 * @param {string} type - Data type
 * @returns {Promise<Object>} Usernames response
 */
export async function fetchAllUsernames(type) {
    return apiRequest(`/get_all_usernames?type=${type}`);
}

/**
 * Fetch user preview
 * @param {string} username - GitHub username
 * @returns {Promise<Object>} User data
 */
export async function fetchUserPreview(username) {
    return apiRequest(`/api/user/${username}/preview`);
}

/**
 * Check if user follows viewer
 * @param {string} username - GitHub username
 * @returns {Promise<Object>} Follow status
 */
export async function checkFollow(username) {
    return apiRequest(`/check_follow?username=${encodeURIComponent(username)}`);
}

// ===== User Actions =====

/**
 * Follow a user
 * @param {string} username - Username to follow
 * @returns {Promise<Object>} Result
 */
export async function followUser(username) {
    return apiRequest(`/follow/${username}`, { method: 'POST' });
}

/**
 * Unfollow a user
 * @param {string} username - Username to unfollow
 * @returns {Promise<Object>} Result
 */
export async function unfollowUser(username) {
    return apiRequest(`/unfollow/${username}`, { method: 'POST' });
}

/**
 * Bulk follow users
 * @param {string[]} usernames - Usernames to follow
 * @param {boolean} dryRun - Whether to perform a dry run
 * @returns {Promise<Object>} Results
 */
export async function bulkFollow(usernames, dryRun = false) {
    return apiRequest('/bulk_follow', {
        method: 'POST',
        body: JSON.stringify({ usernames, dry_run: dryRun })
    });
}

/**
 * Bulk unfollow users
 * @param {string[]} usernames - Usernames to unfollow
 * @param {boolean} dryRun - Whether to perform a dry run
 * @returns {Promise<Object>} Results
 */
export async function bulkUnfollow(usernames, dryRun = false) {
    return apiRequest('/bulk_unfollow', {
        method: 'POST',
        body: JSON.stringify({ usernames, dry_run: dryRun })
    });
}

// ===== Sync Operations =====

/**
 * Trigger a sync operation
 * @param {string} type - Sync type ('all', 'followers', 'following')
 * @returns {Promise<Object>} Sync result
 */
export async function triggerSync(type = 'all') {
    return apiRequest('/api/sync', {
        method: 'POST',
        body: JSON.stringify({ type })
    });
}

/**
 * Get sync status
 * @returns {Promise<Object>} Sync status
 */
export async function getSyncStatus() {
    return apiRequest('/api/sync/status');
}

// ===== Ignore List & Whitelist =====

/**
 * Get ignore list
 * @returns {Promise<Object>} Ignore list
 */
export async function getIgnoreList() {
    return apiRequest('/api/ignore-list');
}

/**
 * Add to ignore list
 * @param {string} username - Username to add
 * @returns {Promise<Object>} Updated list
 */
export async function addToIgnoreList(username) {
    return apiRequest('/api/ignore-list', {
        method: 'POST',
        body: JSON.stringify({ username })
    });
}

/**
 * Remove from ignore list
 * @param {string} username - Username to remove
 * @returns {Promise<Object>} Updated list
 */
export async function removeFromIgnoreList(username) {
    return apiRequest('/api/ignore-list', {
        method: 'DELETE',
        body: JSON.stringify({ username })
    });
}

/**
 * Get whitelist
 * @returns {Promise<Object>} Whitelist
 */
export async function getWhitelist() {
    return apiRequest('/api/whitelist');
}

/**
 * Add to whitelist
 * @param {string} username - Username to add
 * @returns {Promise<Object>} Updated list
 */
export async function addToWhitelist(username) {
    return apiRequest('/api/whitelist', {
        method: 'POST',
        body: JSON.stringify({ username })
    });
}

/**
 * Remove from whitelist
 * @param {string} username - Username to remove
 * @returns {Promise<Object>} Updated list
 */
export async function removeFromWhitelist(username) {
    return apiRequest('/api/whitelist', {
        method: 'DELETE',
        body: JSON.stringify({ username })
    });
}

// ===== Analytics =====

/**
 * Get analytics data
 * @param {number} days - Number of days
 * @returns {Promise<Object>} Analytics data
 */
export async function getAnalytics(days = 30) {
    return apiRequest(`/api/analytics?days=${days}`);
}

// ===== Rate Limit =====

/**
 * Get rate limit status
 * @returns {Promise<Object>} Rate limit info
 */
export async function getRateLimit() {
    return apiRequest('/api/rate-limit');
}
