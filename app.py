"""
GitHub Followers Tracker - Main Application
A comprehensive tool for tracking and managing GitHub followers.
"""
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify
from decouple import config
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import math

# Import from src modules
from src.core.github_api import (
    get_followers,
    get_following,
    follow_user,
    unfollow_user,
    bulk_follow_users,
    bulk_unfollow_users,
    get_followers_with_counts,
    get_users_info,
    get_random_users,
    check_if_user_follows_viewer,
    get_rate_limit_status,
)
from src.services.data_manager import (
    load_previous_followers,
    save_followers,
    load_new_followers,
    save_new_followers,
    load_ignore_list,
    add_to_ignore_list,
    remove_from_ignore_list,
)
from src.core.database import (
    init_db, get_or_create_account, record_follower_event, take_daily_snapshot, log_action,
    sync_followers, sync_following, get_cached_followers, get_cached_following,
    get_cached_new_followers, get_cached_unfollowers, get_cached_not_following_back,
    is_cache_stale, get_all_sync_status, get_sync_status
)
from src.tasks.daily import run_daily_tasks
from src.tasks.monthly import run_monthly_tasks
from src.api.docs import api_docs
from src.api.routes import api
from src.services.notifications import notification_service

app = Flask(__name__)

# Register blueprints for API documentation and extended routes
app.register_blueprint(api_docs)
app.register_blueprint(api)

GITHUB_USERNAME = config('GITHUB_USERNAME')
GITHUB_TOKEN = config('GITHUB_TOKEN')

LOG_FILE = 'logs/app.log'

# Ensure directories exist
import os
os.makedirs('logs', exist_ok=True)
os.makedirs('data', exist_ok=True)

# Set up logging configuration
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Create handlers
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Reduce console noise

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
file_handler.setLevel(logging.DEBUG)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add the handlers to the logger
if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

# Initialize database and create default account
init_db()
DEFAULT_ACCOUNT_ID = get_or_create_account(GITHUB_USERNAME, GITHUB_TOKEN, is_default=True)

# Initialize the scheduler
scheduler = BackgroundScheduler()

# Schedule the daily task at 6 am every day
scheduler.add_job(run_daily_tasks, 'cron', hour=6, id='daily_follow')

# Schedule the monthly task at 1 am on the first day of each month
scheduler.add_job(run_monthly_tasks, 'cron', day=1, hour=1, id='monthly_unfollow')

# ============== SYNC FUNCTIONS ==============

def perform_sync(sync_type: str = 'all'):
    """
    Perform sync of followers/following from GitHub API to database.
    This is the main function that refreshes the cache.
    """
    try:
        logger.info(f"Starting sync: {sync_type}")

        if sync_type in ('all', 'followers'):
            # Fetch followers with counts from API
            followers_data = get_followers_with_counts()
            sync_followers(DEFAULT_ACCOUNT_ID, followers_data)

        if sync_type in ('all', 'following'):
            # Fetch following from API
            following_data = get_following()
            sync_following(DEFAULT_ACCOUNT_ID, following_data)

        logger.info(f"Sync completed: {sync_type}")
        return True
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return False


def ensure_cache_fresh(sync_type: str = 'followers'):
    """Check if cache is stale and sync if needed."""
    if is_cache_stale(DEFAULT_ACCOUNT_ID, sync_type):
        logger.info(f"Cache stale for {sync_type}, syncing...")
        perform_sync(sync_type)


# Schedule daily snapshot at midnight
def take_snapshot():
    """Take daily snapshot of follower counts."""
    try:
        # First sync to get fresh data
        perform_sync('all')

        # Get counts from cache
        followers = get_cached_followers(DEFAULT_ACCOUNT_ID)
        following = get_cached_following(DEFAULT_ACCOUNT_ID)
        new_followers = get_cached_new_followers(DEFAULT_ACCOUNT_ID, days=1)
        unfollowers = get_cached_unfollowers(DEFAULT_ACCOUNT_ID, days=1)

        take_daily_snapshot(
            DEFAULT_ACCOUNT_ID,
            len(followers),
            len(following),
            new_followers=len(new_followers),
            lost_followers=len(unfollowers)
        )
    except Exception as e:
        logger.error(f"Error taking snapshot: {e}")


# Background sync job - runs every 15 minutes
def background_sync():
    """Background job to keep cache fresh."""
    try:
        perform_sync('all')
    except Exception as e:
        logger.error(f"Background sync failed: {e}")


scheduler.add_job(take_snapshot, 'cron', hour=0, minute=5, id='daily_snapshot')
scheduler.add_job(background_sync, 'interval', minutes=15, id='background_sync')

# Start the scheduler
scheduler.start()

# Ensure Flask shuts down gracefully
atexit.register(lambda: scheduler.shutdown())


def _is_valid_github_username(username):
    """Validate GitHub username format."""
    if not username or not isinstance(username, str):
        return False
    if len(username) > 39 or len(username) < 1:
        return False
    if username.startswith('-'):
        return False
    return all(c.isalnum() or c == '-' for c in username)


def paginate_list(items, page, per_page):
    """Paginate a list of items."""
    total = len(items)
    total_pages = math.ceil(total / per_page) if per_page > 0 else 1
    start = (page - 1) * per_page
    end = start + per_page
    return {
        'items': items[start:end],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
    }


def filter_and_sort(items, search=None, sort_by='username', order='asc'):
    """Filter and sort a list of user items."""
    # Filter by search term
    if search:
        search = search.lower()
        items = [
            item for item in items
            if search in (item.get('login') or item).lower()
        ]

    # Sort
    if items and isinstance(items[0], dict):
        if sort_by == 'username':
            items.sort(key=lambda x: x.get('login', '').lower(), reverse=(order == 'desc'))
        elif sort_by == 'followers':
            items.sort(key=lambda x: x.get('followers', 0), reverse=(order == 'desc'))
        elif sort_by == 'following':
            items.sort(key=lambda x: x.get('following', 0), reverse=(order == 'desc'))
        elif sort_by == 'difference':
            items.sort(key=lambda x: x.get('difference', 0), reverse=(order == 'desc'))
    else:
        # List of strings
        items.sort(reverse=(order == 'desc'))

    return items


@app.route('/')
def index():
    logger.info('Loading index page')
    return render_template('index.html')


@app.route('/get_data')
def get_data():
    data_type = request.args.get('type')
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    logger.info(f'Fetching data for {data_type} (refresh={force_refresh})')

    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)

    # Search and sort parameters
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'username')
    order = request.args.get('order', 'asc')

    ignore_list = load_ignore_list()

    try:
        # Check if we need to sync (cache stale or forced refresh)
        if force_refresh or is_cache_stale(DEFAULT_ACCOUNT_ID, 'followers'):
            perform_sync('all')

        if data_type == 'followers':
            # Get followers from database cache
            current_followers = get_cached_followers(DEFAULT_ACCOUNT_ID)
            current_followers = [user for user in current_followers if user['login'].lower() not in ignore_list]

            current_followers = filter_and_sort(current_followers, search, sort_by, order)
            result = paginate_list(current_followers, page, per_page)

            sync_status = get_sync_status(DEFAULT_ACCOUNT_ID, 'followers')

            return jsonify({
                'followers': result['items'],
                'pagination': result['pagination'],
                'total_count': result['pagination']['total'],
                'sync_status': sync_status
            })

        elif data_type == 'following':
            # Get following from database cache
            current_following = get_cached_following(DEFAULT_ACCOUNT_ID)
            current_following = [f for f in current_following if f['login'].lower() not in ignore_list]

            current_following = filter_and_sort(current_following, search, sort_by, order)
            result = paginate_list(current_following, page, per_page)

            sync_status = get_sync_status(DEFAULT_ACCOUNT_ID, 'following')

            return jsonify({
                'following': result['items'],
                'pagination': result['pagination'],
                'total_count': result['pagination']['total'],
                'sync_status': sync_status
            })

        elif data_type == 'new_followers':
            # Get new followers from database cache (last 3 days)
            new_followers = get_cached_new_followers(DEFAULT_ACCOUNT_ID, days=3)
            new_followers = [user for user in new_followers if user['login'].lower() not in ignore_list]

            new_followers = filter_and_sort(new_followers, search, sort_by, order)
            result = paginate_list(new_followers, page, per_page)

            return jsonify({
                'new_followers': result['items'],
                'pagination': result['pagination'],
                'total_count': result['pagination']['total']
            })

        elif data_type == 'unfollowers':
            # Get unfollowers from database cache (last 30 days)
            unfollowers = get_cached_unfollowers(DEFAULT_ACCOUNT_ID, days=30)
            unfollowers = [user for user in unfollowers if user['login'].lower() not in ignore_list]

            unfollowers = filter_and_sort(unfollowers, search, sort_by, order)
            result = paginate_list(unfollowers, page, per_page)

            return jsonify({
                'unfollowers': result['items'],
                'pagination': result['pagination'],
                'total_count': result['pagination']['total']
            })

        elif data_type == 'not_following_back':
            # Get not following back from database cache
            not_following_back = get_cached_not_following_back(DEFAULT_ACCOUNT_ID)
            not_following_back = [user for user in not_following_back if user['login'].lower() not in ignore_list]

            not_following_back = filter_and_sort(not_following_back, search, sort_by, order)
            result = paginate_list(not_following_back, page, per_page)

            return jsonify({
                'not_following_back': result['items'],
                'pagination': result['pagination'],
                'total_count': result['pagination']['total']
            })

        elif data_type == 'suggested_users':
            # Suggested users still come from API (not cached in same way)
            random_users = get_random_users()
            random_users = [user for user in random_users if user['login'].lower() not in ignore_list]

            for user in random_users:
                user['avatar_url'] = f"https://github.com/{user['login']}.png?size=40"

            random_users = filter_and_sort(random_users, search, sort_by, order)
            result = paginate_list(random_users, page, per_page)

            return jsonify({
                'suggested_users': result['items'],
                'pagination': result['pagination'],
                'total_count': result['pagination']['total']
            })

        elif data_type == 'users_more_following':
            followers_with_counts = get_followers_with_counts()
            users_more_following = [
                {
                    'login': follower['login'],
                    'followers': follower['followers'],
                    'following': follower['following'],
                    'difference': follower['following'] - follower['followers'],
                    'avatar_url': f"https://github.com/{follower['login']}.png?size=40"
                }
                for follower in followers_with_counts
                if (follower['following'] - follower['followers'] >= 25) and follower['login'].lower() not in ignore_list
            ]

            users_more_following = filter_and_sort(users_more_following, search, 'difference', 'desc')
            result = paginate_list(users_more_following, page, per_page)

            return jsonify({
                'users_more_following': result['items'],
                'pagination': result['pagination'],
                'total_count': result['pagination']['total']
            })

        else:
            logger.error(f'Invalid data type requested: {data_type}')
            return jsonify({'error': 'Invalid data type requested'}), 400

    except Exception as e:
        logger.exception(f"Error fetching data for {data_type}: {e}")
        return jsonify({'error': 'An error occurred while fetching data'}), 500


@app.route('/bulk_follow', methods=['POST'])
def bulk_follow():
    data = request.get_json(silent=True) or {}
    usernames = data.get('usernames', [])
    dry_run = data.get('dry_run', False)

    logger.info(f'Attempting to bulk follow users: {usernames} (dry_run={dry_run})')

    if dry_run:
        return jsonify({
            'dry_run': True,
            'would_follow': usernames
        })

    results = bulk_follow_users(usernames)

    # Log actions
    log_action(DEFAULT_ACCOUNT_ID, 'bulk_follow', target_usernames=usernames,
               success=all(r.get('success') for r in results.values()))

    return jsonify(results)


@app.route('/bulk_unfollow', methods=['POST'])
def bulk_unfollow():
    data = request.get_json(silent=True) or {}
    usernames = data.get('usernames', [])
    dry_run = data.get('dry_run', False)

    logger.info(f'Attempting to bulk unfollow users: {usernames} (dry_run={dry_run})')

    if dry_run:
        return jsonify({
            'dry_run': True,
            'would_unfollow': usernames
        })

    results = bulk_unfollow_users(usernames)

    # Log actions
    log_action(DEFAULT_ACCOUNT_ID, 'bulk_unfollow', target_usernames=usernames,
               success=all(r.get('success') for r in results.values()))

    return jsonify(results)


@app.route('/unfollow/<username>', methods=['POST'])
def unfollow(username):
    if not _is_valid_github_username(username):
        logger.warning(f'Invalid username format: {username}')
        return jsonify({'success': False, 'message': 'Invalid username format'}), 400

    logger.info(f'Attempting to unfollow user: {username}')
    success, message = unfollow_user(username)

    if success:
        log_action(DEFAULT_ACCOUNT_ID, 'unfollow', target_username=username)
        record_follower_event(DEFAULT_ACCOUNT_ID, username, 'you_unfollowed')
        return jsonify({'success': True})
    else:
        log_action(DEFAULT_ACCOUNT_ID, 'unfollow', target_username=username, success=False, error_message=message)
        return jsonify({'success': False, 'message': message}), 500


@app.route('/follow/<username>', methods=['POST'])
def follow(username):
    if not _is_valid_github_username(username):
        logger.warning(f'Invalid username format: {username}')
        return jsonify({'success': False, 'message': 'Invalid username format'}), 400

    logger.info(f'Attempting to follow user: {username}')
    success, message = follow_user(username)

    if success:
        log_action(DEFAULT_ACCOUNT_ID, 'follow', target_username=username)
        record_follower_event(DEFAULT_ACCOUNT_ID, username, 'you_followed')
        return jsonify({'success': True})
    else:
        log_action(DEFAULT_ACCOUNT_ID, 'follow', target_username=username, success=False, error_message=message)
        return jsonify({'success': False, 'message': message}), 500


@app.route('/get_all_usernames')
def get_all_usernames():
    """Get all usernames for a data type (no pagination) for bulk operations."""
    data_type = request.args.get('type')
    logger.info(f'Fetching all usernames for {data_type}')

    ignore_list = load_ignore_list()

    try:
        # Ensure cache is fresh
        if is_cache_stale(DEFAULT_ACCOUNT_ID, 'followers'):
            perform_sync('all')

        if data_type == 'followers':
            cached = get_cached_followers(DEFAULT_ACCOUNT_ID)
            usernames = [u['login'] for u in cached if u['login'].lower() not in ignore_list]
            return jsonify({'usernames': usernames, 'count': len(usernames)})

        elif data_type == 'following':
            cached = get_cached_following(DEFAULT_ACCOUNT_ID)
            usernames = [f['login'] for f in cached if f['login'].lower() not in ignore_list]
            return jsonify({'usernames': usernames, 'count': len(usernames)})

        elif data_type == 'not_following_back':
            not_following_back = get_cached_not_following_back(DEFAULT_ACCOUNT_ID)
            usernames = [f['login'] for f in not_following_back if f['login'].lower() not in ignore_list]
            return jsonify({'usernames': usernames, 'count': len(usernames)})

        elif data_type == 'unfollowers':
            unfollowers = get_cached_unfollowers(DEFAULT_ACCOUNT_ID, days=30)
            usernames = [u['login'] for u in unfollowers if u['login'].lower() not in ignore_list]
            return jsonify({'usernames': usernames, 'count': len(usernames)})

        elif data_type == 'new_followers':
            new_followers = get_cached_new_followers(DEFAULT_ACCOUNT_ID, days=3)
            usernames = [u['login'] for u in new_followers if u['login'].lower() not in ignore_list]
            return jsonify({'usernames': usernames, 'count': len(usernames)})

        elif data_type == 'suggested_users':
            random_users = get_random_users()
            usernames = [u['login'] for u in random_users if u['login'].lower() not in ignore_list]
            return jsonify({'usernames': usernames, 'count': len(usernames)})

        else:
            return jsonify({'error': 'Invalid data type'}), 400

    except Exception as e:
        logger.exception(f"Error fetching usernames for {data_type}: {e}")
        return jsonify({'error': 'An error occurred'}), 500


@app.route('/api/sync', methods=['POST'])
def trigger_sync():
    """Manually trigger a sync of followers/following data."""
    data = request.get_json(silent=True) or {}
    sync_type = data.get('type', 'all')  # 'all', 'followers', or 'following'

    if sync_type not in ('all', 'followers', 'following'):
        return jsonify({'error': 'Invalid sync type'}), 400

    try:
        success = perform_sync(sync_type)
        status = get_all_sync_status(DEFAULT_ACCOUNT_ID)

        return jsonify({
            'success': success,
            'sync_status': status
        })
    except Exception as e:
        logger.exception(f"Error during sync: {e}")
        return jsonify({'error': 'Sync failed', 'message': str(e)}), 500


@app.route('/api/sync/status')
def sync_status():
    """Get current sync status for all data types."""
    try:
        status = get_all_sync_status(DEFAULT_ACCOUNT_ID)
        return jsonify(status)
    except Exception as e:
        logger.exception(f"Error getting sync status: {e}")
        return jsonify({'error': 'Failed to get sync status'}), 500


@app.route('/check_follow')
def check_follow():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username parameter is required'}), 400
    logger.info(f'Checking if user {username} follows the viewer')
    try:
        follows_you = check_if_user_follows_viewer(username)
        return jsonify({'username': username, 'follows_you': follows_you})
    except Exception as e:
        logger.exception(f"Error checking if user {username} follows viewer: {e}")
        return jsonify({'error': 'An error occurred while checking the user'}), 500


# Ignore list management endpoints
@app.route('/api/ignore-list', methods=['GET'])
def get_ignore_list():
    try:
        ignore_list = load_ignore_list()
        return jsonify({'ignore_list': ignore_list})
    except Exception as e:
        logger.exception(f"Error loading ignore list: {e}")
        return jsonify({'error': 'Failed to load ignore list'}), 500


@app.route('/api/ignore-list', methods=['POST'])
def add_ignore():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    try:
        updated = add_to_ignore_list(username)
        return jsonify({'ignore_list': updated})
    except Exception as e:
        logger.exception(f"Error adding to ignore list: {e}")
        return jsonify({'error': 'Failed to add username to ignore list'}), 500


@app.route('/api/ignore-list', methods=['DELETE'])
def remove_ignore():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    try:
        updated = remove_from_ignore_list(username)
        return jsonify({'ignore_list': updated})
    except Exception as e:
        logger.exception(f"Error removing from ignore list: {e}")
        return jsonify({'error': 'Failed to remove username from ignore list'}), 500


@app.route('/api/user/<username>/preview')
def user_preview(username):
    """Get quick preview of a user's profile."""
    if not _is_valid_github_username(username):
        return jsonify({'error': 'Invalid username'}), 400

    try:
        user_info = get_users_info([username])
        if user_info:
            user = user_info[0]
            user['avatar_url'] = f"https://github.com/{username}.png?size=100"
            user['profile_url'] = f"https://github.com/{username}"
            return jsonify(user)
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        logger.exception(f"Error fetching user preview for {username}: {e}")
        return jsonify({'error': 'Failed to fetch user preview'}), 500


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=9999)
