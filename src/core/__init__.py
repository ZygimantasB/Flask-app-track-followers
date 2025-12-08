"""
Core module - Database models and GitHub API client
"""
from .database import (
    init_db, get_or_create_account, record_follower_event, take_daily_snapshot,
    log_action, sync_followers, sync_following, get_cached_followers,
    get_cached_following, get_cached_new_followers, get_cached_unfollowers,
    get_cached_not_following_back, is_cache_stale, get_all_sync_status,
    get_sync_status, get_analytics, get_recent_actions
)
from .github_api import (
    get_followers, get_following, follow_user, unfollow_user,
    bulk_follow_users, bulk_unfollow_users, get_followers_with_counts,
    get_users_info, get_random_users, check_if_user_follows_viewer,
    get_rate_limit_status
)

__all__ = [
    # Database
    'init_db', 'get_or_create_account', 'record_follower_event', 'take_daily_snapshot',
    'log_action', 'sync_followers', 'sync_following', 'get_cached_followers',
    'get_cached_following', 'get_cached_new_followers', 'get_cached_unfollowers',
    'get_cached_not_following_back', 'is_cache_stale', 'get_all_sync_status',
    'get_sync_status', 'get_analytics', 'get_recent_actions',
    # GitHub API
    'get_followers', 'get_following', 'follow_user', 'unfollow_user',
    'bulk_follow_users', 'bulk_unfollow_users', 'get_followers_with_counts',
    'get_users_info', 'get_random_users', 'check_if_user_follows_viewer',
    'get_rate_limit_status'
]
