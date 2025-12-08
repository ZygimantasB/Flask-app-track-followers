// Toggle visibility of collapsible elements
function toggleVisibility(id) {
    const element = document.getElementById(id);
    const toggleBtn = document.querySelector(`button[onclick="toggleVisibility('${id}')"] i`);

    if (element.style.maxHeight) {
        element.style.maxHeight = null;
        if (toggleBtn) toggleBtn.className = 'fas fa-chevron-down';
    } else {
        element.style.maxHeight = element.scrollHeight + "px";
        if (toggleBtn) toggleBtn.className = 'fas fa-chevron-up';
    }
}

// Theme toggle functionality
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

// Tab navigation
function openTab(tabId) {
    // Hide all tab panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });

    // Deactivate all tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show the selected tab pane
    document.getElementById(tabId).classList.add('active');

    // Activate the corresponding tab button
    document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
            <p>${message}</p>
        </div>
        <button class="notification-close"><i class="fas fa-times"></i></button>
    `;

    document.body.appendChild(notification);

    // Add event listener to close button
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.classList.add('notification-hide');
        setTimeout(() => {
            notification.remove();
        }, 300);
    });

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (document.body.contains(notification)) {
            notification.classList.add('notification-hide');
            setTimeout(() => {
                if (document.body.contains(notification)) {
                    notification.remove();
                }
            }, 300);
        }
    }, 5000);
}

// Update dashboard summary
function updateDashboardSummary() {
    document.getElementById('followers-count-summary').textContent = 
        document.getElementById('followers-count').textContent;
    document.getElementById('following-count-summary').textContent = 
        document.getElementById('following-count').textContent;
    document.getElementById('new-followers-count-summary').textContent = 
        document.getElementById('new-followers-count').textContent;
    document.getElementById('unfollowers-count-summary').textContent = 
        document.getElementById('unfollowers-count').textContent;
}

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

    // Handle Load Data buttons
    document.querySelectorAll('.load-data-button').forEach(button => {
        button.addEventListener('click', function() {
            const dataType = this.getAttribute('data-type');
            fetchData(dataType);
        });
    });

    // Handle bulk follow/unfollow buttons
    document.getElementById('follow-all-new-followers-button').addEventListener('click', function() {
        bulkAction('new-followers-list', '/bulk_follow');
    });

    document.getElementById('unfollow-all-followers-button').addEventListener('click', function() {
        bulkAction('followers-list', '/bulk_unfollow');
    });

    document.getElementById('unfollow-all-following-button').addEventListener('click', function() {
        bulkAction('following-list', '/bulk_unfollow');
    });

    document.getElementById('unfollow-all-unfollowers-button').addEventListener('click', function() {
        bulkAction('unfollowers-list', '/bulk_unfollow');
    });

    document.getElementById('unfollow-all-not-following-back-button').addEventListener('click', function() {
        bulkAction('not-following-back-list', '/bulk_unfollow');
    });

    document.getElementById('follow-selected-suggested-users-button').addEventListener('click', function() {
        followSelectedUsers();
    });

    // Add this event listener for the "Follow All" button
    document.getElementById('follow-all-suggested-users-button').addEventListener('click', function() {
        followAllSuggestedUsers();
    });

    // Handle Search Form Submission
    const searchForm = document.getElementById('search-form');
    searchForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const username = document.getElementById('search-username').value.trim();
        if (username) {
            searchUser(username);
        }
    });

    async function searchUser(username) {
        try {
            const response = await fetch(`/check_follow?username=${encodeURIComponent(username)}`);
            const data = await response.json();
            const searchResultDiv = document.getElementById('search-result');
            if (data.error) {
                // Use textContent to prevent XSS
                searchResultDiv.textContent = `Error: ${data.error}`;
            } else {
                const followsYouText = data.follows_you ? 'follows you' : 'does not follow you';
                // Use the returned username from server for consistency
                searchResultDiv.textContent = `${data.username || username} ${followsYouText}.`;
            }
        } catch (error) {
            console.error('Error searching user:', error);
            showNotification('Failed to search user', 'error');
        }
    }

    async function fetchData(dataType) {
        try {
            showLoadingIndicator();
            const response = await fetch(`/get_data?type=${dataType}`);

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const data = await response.json();

            if (data.error) {
                showNotification(data.error, 'error');
                return;
            }

            populateData(dataType, data);
            updateDashboardSummary();
            showNotification(`${dataType.replace('_', ' ')} data loaded successfully`, 'success');
        } catch (error) {
            console.error('Error fetching data:', error);
            showNotification(`Failed to load data: ${error.message}`, 'error');
        } finally {
            hideLoadingIndicator();
        }
    }

    async function bulkAction(listId, endpoint) {
        const list = document.getElementById(listId);
        const usernames = Array.from(list.querySelectorAll('.list-item .username')).map(span => span.textContent);

        if (usernames.length === 0) {
            showNotification('No users to process', 'info');
            return;
        }

        try {
            showLoadingIndicator();
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ usernames: usernames })
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const results = await response.json();
            let successCount = 0;
            let failCount = 0;

            usernames.forEach(username => {
                if (results[username] && results[username].success) {
                    const li = list.querySelector(`.list-item[data-username="${username}"]`);
                    if (li) {
                        li.classList.add('fade-out');
                        setTimeout(() => {
                            li.style.display = 'none';
                        }, 500);
                    }
                    successCount++;
                } else {
                    console.error(`Failed to process ${username}: ${results[username]?.message || 'Unknown error'}`);
                    failCount++;
                }
            });

            // Update counts after action
            updateDashboardSummary();

            // Show appropriate notification
            if (successCount > 0 && failCount === 0) {
                showNotification(`Successfully processed ${successCount} users`, 'success');
            } else if (successCount > 0 && failCount > 0) {
                showNotification(`Processed ${successCount} users, failed for ${failCount} users`, 'warning');
            } else {
                showNotification(`Failed to process any users`, 'error');
            }

        } catch (error) {
            console.error('Error during bulk action:', error);
            showNotification(`Error: ${error.message}`, 'error');
        } finally {
            hideLoadingIndicator();
        }
    }

    async function followSelectedUsers() {
        const list = document.getElementById('suggested-users-list');
        const selectedCheckboxes = list.querySelectorAll('.list-item input[type="checkbox"]:checked');
        const usernames = Array.from(selectedCheckboxes).map(checkbox => checkbox.dataset.username);

        if (usernames.length === 0) {
            showNotification('No users selected', 'info');
            return;
        }

        try {
            showLoadingIndicator();
            const response = await fetch('/bulk_follow', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ usernames: usernames })
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const results = await response.json();
            let successCount = 0;
            let failCount = 0;

            usernames.forEach(username => {
                if (results[username] && results[username].success) {
                    const li = list.querySelector(`.list-item[data-username="${username}"]`);
                    if (li) {
                        li.classList.add('fade-out');
                        setTimeout(() => {
                            li.style.display = 'none';
                        }, 500);
                    }
                    successCount++;
                } else {
                    console.error(`Failed to follow ${username}: ${results[username]?.message || 'Unknown error'}`);
                    failCount++;
                }
            });

            // Update counts after action
            updateDashboardSummary();

            // Show appropriate notification
            if (successCount > 0 && failCount === 0) {
                showNotification(`Successfully followed ${successCount} users`, 'success');
            } else if (successCount > 0 && failCount > 0) {
                showNotification(`Followed ${successCount} users, failed for ${failCount} users`, 'warning');
            } else {
                showNotification(`Failed to follow any users`, 'error');
            }

        } catch (error) {
            console.error('Error during following selected users:', error);
            showNotification(`Error: ${error.message}`, 'error');
        } finally {
            hideLoadingIndicator();
        }
    }

    // Function for the "Follow All" action
    async function followAllSuggestedUsers() {
        const list = document.getElementById('suggested-users-list');
        const userItems = list.querySelectorAll('.list-item');
        const usernames = Array.from(userItems).map(li => li.dataset.username);

        if (usernames.length === 0) {
            showNotification('No users available to follow', 'info');
            return;
        }

        // Confirm before following all users
        if (!confirm(`Are you sure you want to follow all ${usernames.length} users?`)) {
            return;
        }

        try {
            showLoadingIndicator();
            const response = await fetch('/bulk_follow', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ usernames: usernames })
            });

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }

            const results = await response.json();
            let successCount = 0;
            let failCount = 0;

            usernames.forEach(username => {
                if (results[username] && results[username].success) {
                    const li = list.querySelector(`.list-item[data-username="${username}"]`);
                    if (li) {
                        li.classList.add('fade-out');
                        setTimeout(() => {
                            li.style.display = 'none';
                        }, 500);
                    }
                    successCount++;
                } else {
                    console.error(`Failed to follow ${username}: ${results[username]?.message || 'Unknown error'}`);
                    failCount++;
                }
            });

            // Update counts after action
            updateDashboardSummary();

            // Show appropriate notification
            if (successCount > 0 && failCount === 0) {
                showNotification(`Successfully followed all ${successCount} users`, 'success');
            } else if (successCount > 0 && failCount > 0) {
                showNotification(`Followed ${successCount} users, failed for ${failCount} users`, 'warning');
            } else {
                showNotification(`Failed to follow any users`, 'error');
            }

        } catch (error) {
            console.error('Error during following all suggested users:', error);
            showNotification(`Error: ${error.message}`, 'error');
        } finally {
            hideLoadingIndicator();
        }
    }

    function populateData(dataType, data) {
        const counts = {
            'followers': 'followers-count',
            'following': 'following-count',
            'new_followers': 'new-followers-count',
            'unfollowers': 'unfollowers-count',
            'not_following_back': 'not-following-back-count',
            'suggested_users': 'suggested-users-count',
            'users_more_following': 'users-more-following-count'
        };

        const lists = {
            'followers': 'followers-list',
            'following': 'following-list',
            'new_followers': 'new-followers-list',
            'unfollowers': 'unfollowers-list',
            'not_following_back': 'not-following-back-list',
            'suggested_users': 'suggested-users-list',
            'users_more_following': 'users-more-following-list'
        };

        const dataKeys = {
            'followers': 'followers',
            'following': 'following',
            'new_followers': 'new_followers',
            'unfollowers': 'unfollowers',
            'not_following_back': 'not_following_back',
            'suggested_users': 'suggested_users',
            'users_more_following': 'users_more_following'
        };

        const countElement = document.getElementById(counts[dataType]);
        const listElement = document.getElementById(lists[dataType]);
        const dataList = data[dataKeys[dataType]];

        // Update counts
        if (countElement) {
            countElement.textContent = dataList.length;

            // Also update the dashboard summary if applicable
            const summaryElement = document.getElementById(`${counts[dataType]}-summary`);
            if (summaryElement) {
                summaryElement.textContent = dataList.length;
            }
        }

        // Clear existing list
        listElement.innerHTML = '';

        // Ensure the list is visible if it has items
        if (dataList.length > 0 && !listElement.style.maxHeight) {
            toggleVisibility(lists[dataType]);
        }

        dataList.forEach(item => {
            const li = document.createElement('li');
            li.className = 'list-item';
            li.dataset.username = item.login || item;

            const userInfoDiv = document.createElement('div');
            userInfoDiv.className = 'user-info';

            const usernameSpan = document.createElement('span');
            usernameSpan.className = 'username';
            usernameSpan.textContent = item.login || item;

            userInfoDiv.appendChild(usernameSpan);

            // Add follower and following counts if available
            if (item.followers !== undefined && item.following !== undefined) {
                const countsSpan = document.createElement('span');
                countsSpan.className = 'counts';
                countsSpan.textContent = ` (Followers: ${item.followers}, Following: ${item.following})`;
                userInfoDiv.appendChild(countsSpan);

                // For "Users Following More Than Followed", show the difference
                if (dataType === 'users_more_following') {
                    const differenceSpan = document.createElement('span');
                    differenceSpan.className = 'difference';
                    const diff = item.following - item.followers;
                    differenceSpan.textContent = ` Difference: ${diff}`;
                    userInfoDiv.appendChild(differenceSpan);
                }
            }

            // Add additional information for suggested users
            if (dataType === 'suggested_users') {
                // Add checkbox for selecting users
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.dataset.username = item.login || item;
                li.appendChild(checkbox);
            }

            li.appendChild(userInfoDiv);

            const buttonGroup = document.createElement('div');
            buttonGroup.className = 'button-group';

            if (['following', 'followers', 'not_following_back', 'unfollowers', 'users_more_following'].includes(dataType)) {
                const unfollowForm = document.createElement('form');
                unfollowForm.action = `/unfollow/${item.login || item}`;
                unfollowForm.method = 'post';
                unfollowForm.className = 'unfollow-form';

                const unfollowButton = document.createElement('button');
                unfollowButton.type = 'submit';
                unfollowButton.className = 'btn-unfollow';
                unfollowButton.textContent = 'Unfollow';

                unfollowForm.appendChild(unfollowButton);
                buttonGroup.appendChild(unfollowForm);
            }

            if (['new_followers'].includes(dataType)) {
                const followForm = document.createElement('form');
                followForm.action = `/follow/${item.login || item}`;
                followForm.method = 'post';
                followForm.className = 'follow-form';

                const followButton = document.createElement('button');
                followButton.type = 'submit';
                followButton.className = 'btn-follow';
                followButton.textContent = 'Follow';

                followForm.appendChild(followButton);
                buttonGroup.appendChild(followForm);
            }

            if (buttonGroup.childElementCount > 0) {
                li.appendChild(buttonGroup);
            }

            listElement.appendChild(li);
        });

        addFormEventListeners();
    }

    function addFormEventListeners() {
        document.querySelectorAll('.unfollow-form').forEach(form => {
            form.addEventListener('submit', function(event) {
                event.preventDefault();
                const username = this.action.split('/').pop();
                fetch(this.action, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            this.parentElement.parentElement.style.display = 'none';
                        } else {
                            alert('Failed to unfollow ' + username);
                        }
                    });
            });
        });

        document.querySelectorAll('.follow-form').forEach(form => {
            form.addEventListener('submit', function(event) {
                event.preventDefault();
                const username = this.action.split('/').pop();
                fetch(this.action, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            this.parentElement.parentElement.style.display = 'none';
                        } else {
                            alert('Failed to follow ' + username);
                        }
                    });
            });
        });
    }

    function showLoadingIndicator() {
        const loadingIndicator = document.getElementById('loading-indicator');
        loadingIndicator.style.display = 'block';
    }

    function hideLoadingIndicator() {
        const loadingIndicator = document.getElementById('loading-indicator');
        loadingIndicator.style.display = 'none';
    }
});


// ===== Ignore List Management (Web UI) =====
async function fetchIgnoreList() {
    const res = await fetch('/api/ignore-list');
    if (!res.ok) throw new Error('Failed to load ignore list');
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    return data.ignore_list || [];
}

function renderIgnoreList(usernames) {
    const listEl = document.getElementById('ignore-list');
    const countEl = document.getElementById('ignore-list-count');
    if (!listEl || !countEl) return;
    listEl.innerHTML = '';
    countEl.textContent = usernames.length;

    if (usernames.length > 0 && !listEl.style.maxHeight) {
        // ensure visible if collapsed
        toggleVisibility('ignore-list');
    }

    usernames.forEach(u => {
        const li = document.createElement('li');
        li.className = 'list-item';
        li.dataset.username = u;

        const infoDiv = document.createElement('div');
        infoDiv.className = 'user-info';
        const span = document.createElement('span');
        span.className = 'username';
        span.textContent = u;
        infoDiv.appendChild(span);
        li.appendChild(infoDiv);

        const btnGroup = document.createElement('div');
        btnGroup.className = 'button-group';
        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn btn-danger';
        removeBtn.type = 'button';
        removeBtn.textContent = 'Remove';
        removeBtn.addEventListener('click', async () => {
            try {
                const updated = await removeIgnoreUsername(u);
                renderIgnoreList(updated);
                showNotification(`Removed ${u} from ignore list`, 'success');
            } catch (e) {
                console.error(e);
                showNotification(`Failed to remove: ${e.message}`, 'error');
            }
        });
        btnGroup.appendChild(removeBtn);
        li.appendChild(btnGroup);

        listEl.appendChild(li);
    });
}

async function addIgnoreUsername(username) {
    const res = await fetch('/api/ignore-list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username })
    });
    if (!res.ok) throw new Error(`Server responded ${res.status}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    return data.ignore_list || [];
}

async function removeIgnoreUsername(username) {
    const res = await fetch('/api/ignore-list', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username })
    });
    if (!res.ok) throw new Error(`Server responded ${res.status}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    return data.ignore_list || [];
}

// Bind events when DOM is ready (separate listener to avoid touching existing code)
document.addEventListener('DOMContentLoaded', function() {
    const section = document.getElementById('ignore-list-section');
    if (!section) return;

    const form = document.getElementById('ignore-list-form');
    const input = document.getElementById('ignore-username-input');
    const refreshBtn = document.getElementById('refresh-ignore-list');

    const load = async () => {
        try {
            const list = await fetchIgnoreList();
            renderIgnoreList(list);
        } catch (e) {
            console.error(e);
            showNotification(`Failed to load ignore list: ${e.message}`, 'error');
        }
    };

    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            load();
        });
    }

    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            const username = (input.value || '').trim();
            if (!username) {
                showNotification('Please enter a username', 'warning');
                return;
            }
            try {
                const updated = await addIgnoreUsername(username);
                input.value = '';
                renderIgnoreList(updated);
                showNotification(`Added ${username} to ignore list`, 'success');
            } catch (e) {
                console.error(e);
                showNotification(`Failed to add: ${e.message}`, 'error');
            }
        });
    }

    // Initial load
    load();
});
