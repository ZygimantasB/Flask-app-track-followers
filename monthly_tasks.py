import logging
from github_api import (
    get_followers,
    get_following,
    bulk_unfollow_users,
)
from data_manager import load_ignore_list

logger = logging.getLogger('monthly_tasks')

def run_monthly_tasks():
    logger.info("Starting monthly tasks")

    # Load ignore list to filter out users we don't want to unfollow
    ignore_list = set(load_ignore_list())
    logger.info(f"Loaded {len(ignore_list)} users in ignore list")

    # Unfollow users who are not following back
    logger.info("Removing users who are not following back")
    current_followers = get_followers()
    current_following = get_following()
    # Use lowercase for case-insensitive comparison
    followers_set = set(f.lower() for f in current_followers)
    following_usernames = [user['login'] for user in current_following]
    not_following_back = [
        user for user in following_usernames
        if user.lower() not in followers_set and user.lower() not in ignore_list
    ]
    logger.info(f"Users not following back (excluding ignored): {len(not_following_back)} users")
    if not_following_back:
        unfollow_results = bulk_unfollow_users(not_following_back)
        success_count = sum(1 for r in unfollow_results.values() if r.get('success'))
        logger.info(f"Unfollow results: {success_count}/{len(not_following_back)} successful")
    else:
        logger.info("No users to unfollow")

    logger.info("Monthly tasks completed")
