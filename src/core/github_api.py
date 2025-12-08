import requests
import logging
import time
import random
from decouple import config
from src.services.cache import chunks, load_cache, save_cache
from functools import lru_cache
import concurrent.futures

logger = logging.getLogger(__name__)

GITHUB_TOKEN = config('GITHUB_TOKEN')
GITHUB_USERNAME = config('GITHUB_USERNAME')

# Use a session for connection pooling and improved performance
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

session = requests.Session()
session.headers.update({
    'Authorization': f'Bearer {GITHUB_TOKEN}',
    'Content-Type': 'application/json',
    'Accept': 'application/vnd.github.v3+json'  # Explicitly requesting v3 API
})

# Configure connection pooling and retries for better performance
retry_strategy = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)
adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=retry_strategy
)
session.mount("https://", adapter)
session.mount("http://", adapter)

# API rate limit management
RATE_LIMIT_THRESHOLD = 100  # Minimum remaining requests before slowing down
MIN_REQUEST_INTERVAL = 0.1  # Minimum time between requests in seconds

# Use a lock for thread-safe throttling
import threading
_throttle_lock = threading.Lock()
_last_request_time = 0

def throttle_requests():
    """Throttle requests to avoid hitting rate limits in a thread-safe manner."""
    global _last_request_time

    with _throttle_lock:
        current_time = time.time()
        elapsed_time = current_time - _last_request_time

        # If we've made a request recently, calculate wait time
        if elapsed_time < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed_time
        else:
            sleep_time = 0

        # Update last request time BEFORE releasing lock
        _last_request_time = current_time + sleep_time

    # Sleep OUTSIDE the lock to allow other threads to proceed
    if sleep_time > 0:
        time.sleep(sleep_time)

def execute_github_graphql_query(query, variables=None, retry_count=3):
    """Execute a GraphQL query with automatic retries and error handling."""
    url = 'https://api.github.com/graphql'
    payload = {'query': query, 'variables': variables or {}}

    # Skip rate limit check for rate limit query itself to avoid recursion
    is_rate_limit_query = 'rateLimit' in query and 'cost' in query and 'remaining' in query

    for attempt in range(retry_count):
        try:
            # Check rate limits before making request, but only if this isn't the rate limit query itself
            if attempt == 0 and not is_rate_limit_query and not check_rate_limit(quiet=True):
                logger.warning("Approaching rate limit, slowing down requests")
                time.sleep(5)  # Wait longer if we're close to the rate limit

            throttle_requests()

            logger.debug(f"Executing GraphQL query (attempt {attempt+1}/{retry_count})")
            response = session.post(url, json=payload)

            if response.status_code == 403:
                logger.error('403 Forbidden: Check your token permissions and rate limits.')
                # Check if we hit rate limit
                if 'rate limit' in response.text.lower():
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0)) - time.time()
                    if reset_time > 0:
                        logger.warning(f"Rate limit exceeded. Waiting {reset_time:.0f} seconds")
                        time.sleep(min(reset_time + 1, 60))  # Wait up to 60 seconds
                        continue
                raise Exception('403 Forbidden: Check your token permissions and rate limits.')

            response.raise_for_status()
            result = response.json()

            if 'errors' in result:
                error_messages = '; '.join([error['message'] for error in result['errors']])
                logger.error(f"GraphQL query failed: {error_messages}")

                # Check for rate limit errors
                if any('rate limit' in error['message'].lower() for error in result['errors']):
                    logger.warning("Rate limit error detected, waiting before retry")
                    time.sleep(10)
                    continue

                raise Exception(f"GraphQL query failed: {error_messages}")

            logger.debug("GraphQL query executed successfully")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f'Request error (attempt {attempt+1}/{retry_count}): {e}')
            if attempt < retry_count - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise

    raise Exception(f"Failed after {retry_count} attempts")

# Cache for rate limit status
_rate_limit_cache = {
    'data': None,
    'timestamp': 0
}
# Cache expiration time in seconds
RATE_LIMIT_CACHE_TTL = 60  # Only check rate limit once per minute

def get_rate_limit_status():
    """Get current rate limit status with caching to avoid unnecessary requests."""
    global _rate_limit_cache

    current_time = time.time()
    # If cache is valid, return cached data
    if _rate_limit_cache['data'] and (current_time - _rate_limit_cache['timestamp'] < RATE_LIMIT_CACHE_TTL):
        return _rate_limit_cache['data']

    # Cache expired or not set, fetch new data
    query = '''
    {
      rateLimit {
        limit
        cost
        remaining
        resetAt
      }
    }
    '''
    result = execute_github_graphql_query(query)
    rate_limit = result['data']['rateLimit']

    # Update cache
    _rate_limit_cache['data'] = rate_limit
    _rate_limit_cache['timestamp'] = current_time

    logger.debug(f"Rate limit status: {rate_limit}")
    return rate_limit

def check_rate_limit(quiet=False):
    """Check if we're approaching the rate limit."""
    try:
        rate_limit = get_rate_limit_status()
        remaining = rate_limit['remaining']
        reset_at = rate_limit['resetAt']

        if not quiet:
            logger.info(f'Rate limit: {remaining} remaining, resets at {reset_at}')

        if remaining < RATE_LIMIT_THRESHOLD:
            logger.warning(f'Approaching rate limit: {remaining} requests remaining until {reset_at}')
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        return True  # Default to true to allow operations to continue

def get_random_users(limit=50, batch_size=100):
    """Fetch random GitHub users efficiently."""
    logger.info(f"Fetching {limit} random users")
    accumulated_users = []
    since = random.randint(1, 10000000)  # Random starting point for more variety

    try:
        # Fetch users in batches
        while len(accumulated_users) < 2000:
            throttle_requests()

            response = session.get(
                f'https://api.github.com/users?per_page={batch_size}&since={since}',
            )

            if response.status_code == 403:
                logger.error('403 Forbidden: Check your token permissions and rate limits.')
                raise Exception('403 Forbidden: Check your token permissions and rate limits.')

            response.raise_for_status()
            users = response.json()

            if not users:
                break  # No more users to fetch

            accumulated_users.extend(users)
            since = users[-1]['id']  # Update 'since' to the last user's ID

            if len(accumulated_users) >= 2000:
                break

            time.sleep(MIN_REQUEST_INTERVAL)  # Respect rate limits

        # Get users we're already following
        following = get_following()
        following_usernames = set(user['login'] for user in following)

        # Filter out users we're already following
        filtered_users = [user for user in accumulated_users if user['login'] not in following_usernames]

        # Fetch user details in parallel
        usernames = [user['login'] for user in filtered_users[:min(300, len(filtered_users))]]
        users_info = get_users_info_parallel(usernames)

        # Filter out organizations and select users with reasonable follower counts
        users_info = [
            user for user in users_info
            if user.get('__typename') == 'User' and
               user.get('followers', 0) >= 5 and  # Users with at least 5 followers
               user.get('following', 0) >= 10     # Users who follow at least 10 people
        ]

        # Select random subset with preference to active users
        if users_info:
            # Sort by activity (more following = more active)
            users_info.sort(key=lambda x: x.get('following', 0), reverse=True)
            # Take top 50% and randomly sample from them
            top_half = users_info[:max(len(users_info) // 2, limit)]
            random_users = random.sample(top_half, min(limit, len(top_half)))
            return random_users
        return []
    except Exception as e:
        logger.error(f'Error fetching random users: {e}')
        return []

def get_users_info_parallel(usernames, max_workers=5):
    """Fetch user info for multiple usernames in parallel."""
    logger.info(f"Fetching info for {len(usernames)} users in parallel")

    if not usernames:
        return []

    # Split usernames into chunks to process in parallel
    username_chunks = list(chunks(usernames, 5))  # 5 users per GraphQL query
    users_info = []

    # Process chunks in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(get_users_info_chunk, chunk) for chunk in username_chunks]

        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                users_info.extend(result)
            except Exception as e:
                logger.error(f'Error in parallel user info fetch: {e}')

    logger.info(f"Successfully fetched info for {len(users_info)} users")
    return users_info

def _sanitize_username(username):
    """Sanitize username for safe use in GraphQL queries.

    GitHub usernames can only contain alphanumeric characters and hyphens,
    and cannot begin with a hyphen.
    """
    if not username or not isinstance(username, str):
        return None
    # GitHub username rules: alphanumeric and hyphens only, max 39 chars
    sanitized = ''.join(c for c in username if c.isalnum() or c == '-')
    if not sanitized or sanitized.startswith('-') or len(sanitized) > 39:
        return None
    return sanitized


def get_users_info_chunk(usernames):
    """Fetch info for a chunk of usernames."""
    if not usernames:
        return []

    # Sanitize all usernames to prevent injection
    sanitized_usernames = []
    for username in usernames:
        sanitized = _sanitize_username(username)
        if sanitized:
            sanitized_usernames.append(sanitized)

    if not sanitized_usernames:
        return []

    try:
        query_fragments = []
        for index, username in enumerate(sanitized_usernames):
            query_fragments.append(f'''
                user_{index}: user(login: "{username}") {{
                    login
                    __typename
                    followers {{
                        totalCount
                    }}
                    following {{
                        totalCount
                    }}
                    bio
                    repositories(privacy: PUBLIC) {{
                        totalCount
                    }}
                }}
            ''')

        query = f'''
        query {{
            {"".join(query_fragments)}
        }}
        '''

        result = execute_github_graphql_query(query)
        data = result.get('data', {})
        users_info = []

        for key in data:
            user_data = data[key]
            if user_data:
                users_info.append({
                    'login': user_data['login'],
                    'followers': user_data['followers']['totalCount'],
                    'following': user_data['following']['totalCount'],
                    'bio': user_data.get('bio', ''),
                    'public_repos': user_data['repositories']['totalCount'],
                    '__typename': user_data['__typename'],
                })

        return users_info
    except Exception as e:
        logger.error(f'Error fetching user info chunk: {e}')
        return []

def get_users_info(usernames):
    """Backwards compatibility wrapper for get_users_info_parallel."""
    return get_users_info_parallel(usernames)

def follow_user(username):
    """Follow a GitHub user."""
    logger.debug(f"Attempting to follow {username}")
    owner_id, owner_type = get_repository_owner_id(username)

    if not owner_id:
        logger.error(f"User not found: {username}")
        return False, 'User not found'

    if owner_type != 'User':
        logger.error(f"Cannot follow {username} because they are not a user")
        return False, 'Cannot follow organizations automatically'

    mutation = '''
    mutation ($userId: ID!) {
      followUser(input: {userId: $userId}) {
        clientMutationId
      }
    }
    '''

    variables = {'userId': owner_id}

    try:
        execute_github_graphql_query(mutation, variables)
        logger.info(f"Successfully followed {username}")
        return True, ''
    except Exception as e:
        logger.error(f'Error following {username}: {e}')
        return False, str(e)

def unfollow_user(username):
    """Unfollow a GitHub user or organization."""
    logger.debug(f"Attempting to unfollow {username}")
    owner_id, owner_type = get_repository_owner_id(username)

    if not owner_id:
        logger.error(f"User not found: {username}")
        return False, 'User not found'

    if owner_type == 'User':
        mutation = '''
        mutation ($userId: ID!) {
          unfollowUser(input: {userId: $userId}) {
            clientMutationId
          }
        }
        '''
        variables = {'userId': owner_id}
    elif owner_type == 'Organization':
        mutation = '''
        mutation ($organizationId: ID!) {
          unfollowOrganization(input: {organizationId: $organizationId}) {
            clientMutationId
          }
        }
        '''
        variables = {'organizationId': owner_id}
    else:
        logger.error(f"Unsupported owner type for {username}: {owner_type}")
        return False, 'Unsupported owner type'

    try:
        execute_github_graphql_query(mutation, variables)
        logger.info(f"Successfully unfollowed {username}")
        return True, ''
    except Exception as e:
        logger.error(f'Error unfollowing {username}: {e}')
        return False, str(e)

def bulk_follow_users(usernames, max_workers=3):
    """Follow multiple users in parallel."""
    logger.info(f"Bulk following {len(usernames)} users")
    results = {}

    if not usernames:
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_username = {executor.submit(follow_user, username): username for username in usernames}

        for future in concurrent.futures.as_completed(future_to_username):
            username = future_to_username[future]
            try:
                success, message = future.result()
                results[username] = {'success': success, 'message': message}
                # Small delay to prevent overwhelming the API
                time.sleep(0.5)
            except Exception as e:
                logger.error(f'Error in bulk follow for {username}: {e}')
                results[username] = {'success': False, 'message': str(e)}

    return results

def bulk_unfollow_users(usernames, max_workers=3):
    """Unfollow multiple users in parallel."""
    logger.info(f"Bulk unfollowing {len(usernames)} users")
    results = {}

    if not usernames:
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_username = {executor.submit(unfollow_user, username): username for username in usernames}

        for future in concurrent.futures.as_completed(future_to_username):
            username = future_to_username[future]
            try:
                success, message = future.result()
                results[username] = {'success': success, 'message': message}
                # Small delay to prevent overwhelming the API
                time.sleep(0.5)
            except Exception as e:
                logger.error(f'Error in bulk unfollow for {username}: {e}')
                results[username] = {'success': False, 'message': str(e)}

    return results

def get_repository_owner_id(username):
    """Get the ID and type of a GitHub user or organization."""
    logger.debug(f"Fetching repository owner ID for {username}")

    # Check cache first
    cache = load_cache()
    cache_key = f"owner_id_{username}"

    if cache_key in cache:
        logger.debug(f"Found cached owner ID for {username}")
        return cache[cache_key]['id'], cache[cache_key]['type']

    # If not in cache, fetch from API
    query = '''
    query ($username: String!) {
      repositoryOwner(login: $username) {
        id
        __typename
      }
    }
    '''
    variables = {'username': username}

    try:
        result = execute_github_graphql_query(query, variables)
        owner = result['data']['repositoryOwner']

        if owner:
            # Cache the result
            cache[cache_key] = {
                'id': owner['id'],
                'type': owner['__typename'],
                'timestamp': time.time()
            }
            save_cache(cache)

            logger.debug(f"Found repository owner ID for {username}: {owner['id']}")
            return owner['id'], owner['__typename']
        else:
            logger.warning(f"Repository owner not found for {username}")
            return None, None
    except Exception as e:
        logger.error(f'Error fetching repository owner ID for {username}: {e}')
        return None, None

def get_followers_with_counts(batch_size=100):
    """Get followers with follower/following counts."""
    logger.info("Fetching followers with counts")
    followers = []
    cursor = None
    # Ensure batch_size is within GitHub's limits (max 100)
    batch_size = min(max(1, batch_size), 100)

    while True:
        try:
            query = f'''
            query ($cursor: String) {{
              viewer {{
                followers(first: {batch_size}, after: $cursor) {{
                  nodes {{
                    login
                    followers {{
                      totalCount
                    }}
                    following {{
                      totalCount
                    }}
                  }}
                  pageInfo {{
                    hasNextPage
                    endCursor
                  }}
                }}
              }}
            }}
            '''
            variables = {'cursor': cursor}
            result = execute_github_graphql_query(query, variables)
            viewer = result['data']['viewer']

            batch_followers = [
                {
                    'login': node['login'],
                    'followers': node['followers']['totalCount'],
                    'following': node['following']['totalCount']
                }
                for node in viewer['followers']['nodes']
            ]

            followers.extend(batch_followers)
            logger.debug(f"Fetched {len(batch_followers)} followers in this batch")

            if viewer['followers']['pageInfo']['hasNextPage']:
                cursor = viewer['followers']['pageInfo']['endCursor']
                time.sleep(MIN_REQUEST_INTERVAL)
            else:
                break

        except Exception as e:
            logger.error(f'Error fetching followers with counts: {e}')
            break

    logger.info(f"Total followers fetched: {len(followers)}")
    return followers

def get_followers(batch_size=100):
    """Get usernames of followers."""
    logger.info("Fetching followers")
    followers = []
    cursor = None
    # Ensure batch_size is within GitHub's limits (max 100)
    batch_size = min(max(1, batch_size), 100)

    while True:
        try:
            query = f'''
            query ($cursor: String) {{
              viewer {{
                followers(first: {batch_size}, after: $cursor) {{
                  nodes {{
                    login
                  }}
                  pageInfo {{
                    hasNextPage
                    endCursor
                  }}
                }}
              }}
            }}
            '''
            variables = {'cursor': cursor}
            result = execute_github_graphql_query(query, variables)
            viewer = result['data']['viewer']

            batch_followers = [node['login'] for node in viewer['followers']['nodes']]
            followers.extend(batch_followers)

            logger.debug(f"Fetched {len(batch_followers)} followers in this batch")

            if viewer['followers']['pageInfo']['hasNextPage']:
                cursor = viewer['followers']['pageInfo']['endCursor']
                time.sleep(MIN_REQUEST_INTERVAL)
            else:
                break

        except Exception as e:
            logger.error(f'Error fetching followers: {e}')
            break

    logger.info(f"Total followers fetched: {len(followers)}")
    return followers

def get_following(batch_size=100):
    """Get users being followed with additional metadata."""
    logger.info("Fetching following")
    following = []
    cursor = None
    # Ensure batch_size is within GitHub's limits (max 100)
    batch_size = min(max(1, batch_size), 100)

    while True:
        try:
            query = f'''
            query ($cursor: String) {{
              viewer {{
                following(first: {batch_size}, after: $cursor) {{
                  nodes {{
                    login
                    __typename
                    id
                    followers {{
                        totalCount
                    }}
                    following {{
                        totalCount
                    }}
                  }}
                  pageInfo {{
                    hasNextPage
                    endCursor
                  }}
                }}
              }}
            }}
            '''
            variables = {'cursor': cursor}
            result = execute_github_graphql_query(query, variables)
            viewer = result['data']['viewer']

            batch_following = [
                {
                    'login': node['login'],
                    'type': node['__typename'],
                    'id': node['id'],
                    'followers': node['followers']['totalCount'],
                    'following': node['following']['totalCount']
                }
                for node in viewer['following']['nodes']
            ]

            following.extend(batch_following)
            logger.debug(f"Fetched {len(batch_following)} following in this batch")

            if viewer['following']['pageInfo']['hasNextPage']:
                cursor = viewer['following']['pageInfo']['endCursor']
                time.sleep(MIN_REQUEST_INTERVAL)
            else:
                break

        except Exception as e:
            logger.error(f'Error fetching following: {e}')
            break

    logger.info(f"Total following fetched: {len(following)}")
    return following

def check_if_user_follows_viewer(username):
    """Check if a specific user follows the viewer."""
    logger.debug(f"Checking if user {username} follows the viewer")

    # Check cache first
    cache = load_cache()
    cache_key = f"follows_viewer_{username}"
    cache_ttl = 60 * 60 * 24  # 1 day in seconds

    if cache_key in cache and (time.time() - cache.get(cache_key, {}).get('timestamp', 0) < cache_ttl):
        logger.debug(f"Found cached follows status for {username}")
        return cache[cache_key]['follows']

    # If not in cache, fetch from API
    query = '''
    query ($username: String!) {
      user(login: $username) {
        isFollowingViewer
      }
    }
    '''
    variables = {'username': username}

    try:
        result = execute_github_graphql_query(query, variables)
        user_data = result['data']['user']

        if user_data is None:
            logger.error(f"User {username} not found")
            raise Exception('User not found')

        follows_viewer = user_data['isFollowingViewer']

        # Cache the result
        cache[cache_key] = {
            'follows': follows_viewer,
            'timestamp': time.time()
        }
        save_cache(cache)

        logger.debug(f"User {username} follows viewer: {follows_viewer}")
        return follows_viewer

    except Exception as e:
        logger.error(f'Error checking if user {username} follows viewer: {e}')
        raise
