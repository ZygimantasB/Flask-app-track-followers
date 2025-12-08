"""
Daily scheduled tasks for GitHub Followers Tracker.
"""
import logging
from src.core.github_api import bulk_follow_users, get_random_users

logger = logging.getLogger('daily_tasks')


def run_daily_tasks():
    """Execute daily tasks - follow suggested users."""
    logger.info("Starting daily tasks")

    # Get suggested users
    suggested_users = get_random_users()
    logger.info(f"Fetched {len(suggested_users)} suggested users")

    # Select 50 random users
    if suggested_users:
        usernames = [user['login'] for user in suggested_users]
        selected_usernames = usernames  # We already fetched 50 users

        # Follow these users
        logger.info(f"Following {len(selected_usernames)} users: {selected_usernames}")
        results = bulk_follow_users(selected_usernames)
        logger.info(f"Follow results: {results}")
    else:
        logger.info("No suggested users available to follow")

    logger.info("Daily tasks completed")
