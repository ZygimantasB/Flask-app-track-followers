"""
Unit tests for GitHub API module.
"""
import pytest
from unittest.mock import patch, Mock, MagicMock
import time


class TestUsernameValidation:
    """Tests for username sanitization and validation."""

    def test_sanitize_valid_username(self):
        """Test sanitization of valid usernames."""
        from src.core.github_api import _sanitize_username

        assert _sanitize_username('validuser') == 'validuser'
        assert _sanitize_username('valid-user') == 'valid-user'
        assert _sanitize_username('user123') == 'user123'
        assert _sanitize_username('a') == 'a'

    def test_sanitize_invalid_username(self):
        """Test sanitization of invalid usernames."""
        from src.core.github_api import _sanitize_username

        assert _sanitize_username('') is None
        assert _sanitize_username(None) is None
        assert _sanitize_username('-startswithhyphen') is None
        assert _sanitize_username('a' * 40) is None  # Too long
        assert _sanitize_username(123) is None  # Not a string

    def test_sanitize_removes_special_chars(self):
        """Test that special characters are removed."""
        from src.core.github_api import _sanitize_username

        # Special chars should be stripped
        assert _sanitize_username('user@name') == 'username'
        assert _sanitize_username('user.name') == 'username'
        assert _sanitize_username('user_name') == 'username'


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_throttle_requests(self):
        """Test request throttling."""
        from src.core.github_api import throttle_requests, MIN_REQUEST_INTERVAL

        start = time.time()
        throttle_requests()
        throttle_requests()
        elapsed = time.time() - start

        # Should have waited at least MIN_REQUEST_INTERVAL
        assert elapsed >= MIN_REQUEST_INTERVAL * 0.9  # Allow small tolerance

    @patch('src.core.github_api.execute_github_graphql_query')
    def test_get_rate_limit_status(self, mock_query):
        """Test getting rate limit status."""
        from src.core.github_api import get_rate_limit_status, _rate_limit_cache

        # Clear cache
        _rate_limit_cache['data'] = None
        _rate_limit_cache['timestamp'] = 0

        mock_query.return_value = {
            'data': {
                'rateLimit': {
                    'limit': 5000,
                    'cost': 1,
                    'remaining': 4999,
                    'resetAt': '2024-01-01T00:00:00Z'
                }
            }
        }

        result = get_rate_limit_status()

        assert result['limit'] == 5000
        assert result['remaining'] == 4999

    @patch('src.core.github_api.get_rate_limit_status')
    def test_check_rate_limit_ok(self, mock_status):
        """Test rate limit check when OK."""
        from src.core.github_api import check_rate_limit, RATE_LIMIT_THRESHOLD

        mock_status.return_value = {
            'remaining': RATE_LIMIT_THRESHOLD + 100,
            'resetAt': '2024-01-01T00:00:00Z'
        }

        assert check_rate_limit(quiet=True) is True

    @patch('src.core.github_api.get_rate_limit_status')
    def test_check_rate_limit_low(self, mock_status):
        """Test rate limit check when low."""
        from src.core.github_api import check_rate_limit, RATE_LIMIT_THRESHOLD

        mock_status.return_value = {
            'remaining': RATE_LIMIT_THRESHOLD - 10,
            'resetAt': '2024-01-01T00:00:00Z'
        }

        assert check_rate_limit(quiet=True) is False


class TestGraphQLExecution:
    """Tests for GraphQL query execution."""

    @patch('src.core.github_api.session')
    @patch('src.core.github_api.throttle_requests')
    def test_execute_graphql_success(self, mock_throttle, mock_session):
        """Test successful GraphQL execution."""
        from src.core.github_api import execute_github_graphql_query

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': {'viewer': {'login': 'test'}}}
        mock_session.post.return_value = mock_response

        result = execute_github_graphql_query('query { viewer { login } }')

        assert result['data']['viewer']['login'] == 'test'
        mock_session.post.assert_called_once()

    @patch('src.core.github_api.session')
    @patch('src.core.github_api.throttle_requests')
    def test_execute_graphql_with_errors(self, mock_throttle, mock_session):
        """Test GraphQL execution with errors."""
        from src.core.github_api import execute_github_graphql_query

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': None,
            'errors': [{'message': 'Some error'}]
        }
        mock_session.post.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            execute_github_graphql_query('query { viewer { login } }')

        assert 'Some error' in str(exc_info.value)

    @patch('src.core.github_api.session')
    @patch('src.core.github_api.throttle_requests')
    @patch('src.core.github_api.time.sleep')
    def test_execute_graphql_retry_on_failure(self, mock_sleep, mock_throttle, mock_session):
        """Test GraphQL retry logic."""
        from src.core.github_api import execute_github_graphql_query
        import requests

        # First call fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 200
        mock_response_fail.raise_for_status.side_effect = requests.exceptions.RequestException("Network error")

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': {'test': 'value'}}

        mock_session.post.side_effect = [
            requests.exceptions.RequestException("Network error"),
            mock_response_success
        ]

        result = execute_github_graphql_query('query { test }')

        assert result['data']['test'] == 'value'
        assert mock_session.post.call_count == 2


class TestFollowersAPI:
    """Tests for follower-related API functions."""

    @patch('src.core.github_api.execute_github_graphql_query')
    def test_get_followers(self, mock_query):
        """Test getting followers list."""
        from src.core.github_api import get_followers

        mock_query.return_value = {
            'data': {
                'viewer': {
                    'followers': {
                        'nodes': [
                            {'login': 'user1'},
                            {'login': 'user2'}
                        ],
                        'pageInfo': {
                            'hasNextPage': False,
                            'endCursor': None
                        }
                    }
                }
            }
        }

        result = get_followers()

        assert len(result) == 2
        assert 'user1' in result
        assert 'user2' in result

    @patch('src.core.github_api.execute_github_graphql_query')
    def test_get_followers_with_counts(self, mock_query):
        """Test getting followers with follower/following counts."""
        from src.core.github_api import get_followers_with_counts

        mock_query.return_value = {
            'data': {
                'viewer': {
                    'followers': {
                        'nodes': [
                            {
                                'login': 'user1',
                                'followers': {'totalCount': 100},
                                'following': {'totalCount': 50}
                            }
                        ],
                        'pageInfo': {
                            'hasNextPage': False,
                            'endCursor': None
                        }
                    }
                }
            }
        }

        result = get_followers_with_counts()

        assert len(result) == 1
        assert result[0]['login'] == 'user1'
        assert result[0]['followers'] == 100
        assert result[0]['following'] == 50

    @patch('src.core.github_api.execute_github_graphql_query')
    def test_get_followers_pagination(self, mock_query):
        """Test followers pagination."""
        from src.core.github_api import get_followers

        # First page
        mock_query.side_effect = [
            {
                'data': {
                    'viewer': {
                        'followers': {
                            'nodes': [{'login': 'user1'}],
                            'pageInfo': {
                                'hasNextPage': True,
                                'endCursor': 'cursor1'
                            }
                        }
                    }
                }
            },
            # Second page
            {
                'data': {
                    'viewer': {
                        'followers': {
                            'nodes': [{'login': 'user2'}],
                            'pageInfo': {
                                'hasNextPage': False,
                                'endCursor': None
                            }
                        }
                    }
                }
            }
        ]

        result = get_followers()

        assert len(result) == 2
        assert mock_query.call_count == 2


class TestFollowingAPI:
    """Tests for following-related API functions."""

    @patch('src.core.github_api.execute_github_graphql_query')
    def test_get_following(self, mock_query):
        """Test getting following list."""
        from src.core.github_api import get_following

        mock_query.return_value = {
            'data': {
                'viewer': {
                    'following': {
                        'nodes': [
                            {
                                'login': 'following1',
                                '__typename': 'User',
                                'id': 'MDQ6VXNlcjEyMzQ1',
                                'followers': {'totalCount': 100},
                                'following': {'totalCount': 50}
                            }
                        ],
                        'pageInfo': {
                            'hasNextPage': False,
                            'endCursor': None
                        }
                    }
                }
            }
        }

        result = get_following()

        assert len(result) == 1
        assert result[0]['login'] == 'following1'
        assert result[0]['type'] == 'User'


class TestFollowUnfollow:
    """Tests for follow/unfollow operations."""

    @patch('src.core.github_api.execute_github_graphql_query')
    @patch('src.core.github_api.get_repository_owner_id')
    def test_follow_user_success(self, mock_get_id, mock_query):
        """Test successful follow."""
        from src.core.github_api import follow_user

        mock_get_id.return_value = ('MDQ6VXNlcjEyMzQ1', 'User')
        mock_query.return_value = {'data': {'followUser': {'clientMutationId': None}}}

        success, message = follow_user('testuser')

        assert success is True
        assert message == ''

    @patch('src.core.github_api.get_repository_owner_id')
    def test_follow_user_not_found(self, mock_get_id):
        """Test following non-existent user."""
        from src.core.github_api import follow_user

        mock_get_id.return_value = (None, None)

        success, message = follow_user('nonexistent')

        assert success is False
        assert 'not found' in message.lower()

    @patch('src.core.github_api.get_repository_owner_id')
    def test_follow_organization_fails(self, mock_get_id):
        """Test that following organizations fails gracefully."""
        from src.core.github_api import follow_user

        mock_get_id.return_value = ('MDEyOk9yZ2FuaXphdGlvbjEyMzQ1', 'Organization')

        success, message = follow_user('some-org')

        assert success is False
        assert 'organization' in message.lower()

    @patch('src.core.github_api.execute_github_graphql_query')
    @patch('src.core.github_api.get_repository_owner_id')
    def test_unfollow_user_success(self, mock_get_id, mock_query):
        """Test successful unfollow."""
        from src.core.github_api import unfollow_user

        mock_get_id.return_value = ('MDQ6VXNlcjEyMzQ1', 'User')
        mock_query.return_value = {'data': {'unfollowUser': {'clientMutationId': None}}}

        success, message = unfollow_user('testuser')

        assert success is True
        assert message == ''

    @patch('src.core.github_api.execute_github_graphql_query')
    @patch('src.core.github_api.get_repository_owner_id')
    def test_unfollow_organization_success(self, mock_get_id, mock_query):
        """Test unfollowing organization."""
        from src.core.github_api import unfollow_user

        mock_get_id.return_value = ('MDEyOk9yZ2FuaXphdGlvbjEyMzQ1', 'Organization')
        mock_query.return_value = {'data': {'unfollowOrganization': {'clientMutationId': None}}}

        success, message = unfollow_user('some-org')

        assert success is True


class TestBulkOperations:
    """Tests for bulk follow/unfollow operations."""

    @patch('src.core.github_api.follow_user')
    def test_bulk_follow_users(self, mock_follow):
        """Test bulk follow."""
        from src.core.github_api import bulk_follow_users

        mock_follow.return_value = (True, '')

        results = bulk_follow_users(['user1', 'user2', 'user3'])

        assert len(results) == 3
        assert all(r['success'] for r in results.values())

    @patch('src.core.github_api.follow_user')
    def test_bulk_follow_partial_failure(self, mock_follow):
        """Test bulk follow with partial failures."""
        from src.core.github_api import bulk_follow_users

        mock_follow.side_effect = [
            (True, ''),
            (False, 'User not found'),
            (True, '')
        ]

        results = bulk_follow_users(['user1', 'user2', 'user3'])

        assert results['user1']['success'] is True
        assert results['user2']['success'] is False
        assert results['user3']['success'] is True

    @patch('src.core.github_api.unfollow_user')
    def test_bulk_unfollow_users(self, mock_unfollow):
        """Test bulk unfollow."""
        from src.core.github_api import bulk_unfollow_users

        mock_unfollow.return_value = (True, '')

        results = bulk_unfollow_users(['user1', 'user2'])

        assert len(results) == 2
        assert all(r['success'] for r in results.values())


class TestUserInfo:
    """Tests for user info fetching."""

    @patch('src.core.github_api.execute_github_graphql_query')
    def test_get_users_info_chunk(self, mock_query):
        """Test getting user info for a chunk of users."""
        from src.core.github_api import get_users_info_chunk

        mock_query.return_value = {
            'data': {
                'user_0': {
                    'login': 'user1',
                    '__typename': 'User',
                    'followers': {'totalCount': 100},
                    'following': {'totalCount': 50},
                    'bio': 'Test bio',
                    'repositories': {'totalCount': 10}
                }
            }
        }

        result = get_users_info_chunk(['user1'])

        assert len(result) == 1
        assert result[0]['login'] == 'user1'
        assert result[0]['followers'] == 100

    def test_get_users_info_chunk_empty(self):
        """Test getting user info with empty list."""
        from src.core.github_api import get_users_info_chunk

        result = get_users_info_chunk([])

        assert result == []

    @patch('src.core.github_api.execute_github_graphql_query')
    @patch('src.core.github_api.load_cache')
    @patch('src.core.github_api.save_cache')
    def test_get_repository_owner_id(self, mock_save, mock_load, mock_query):
        """Test getting repository owner ID."""
        from src.core.github_api import get_repository_owner_id

        mock_load.return_value = {}
        mock_query.return_value = {
            'data': {
                'repositoryOwner': {
                    'id': 'MDQ6VXNlcjEyMzQ1',
                    '__typename': 'User'
                }
            }
        }

        owner_id, owner_type = get_repository_owner_id('testuser')

        assert owner_id == 'MDQ6VXNlcjEyMzQ1'
        assert owner_type == 'User'

    @patch('src.core.github_api.load_cache')
    def test_get_repository_owner_id_cached(self, mock_load):
        """Test getting cached repository owner ID."""
        from src.core.github_api import get_repository_owner_id

        mock_load.return_value = {
            'owner_id_cacheduser': {
                'id': 'MDQ6VXNlcjEyMzQ1',
                'type': 'User',
                'timestamp': 9999999999
            }
        }

        owner_id, owner_type = get_repository_owner_id('cacheduser')

        assert owner_id == 'MDQ6VXNlcjEyMzQ1'
        assert owner_type == 'User'


class TestCheckFollowStatus:
    """Tests for checking follow status."""

    @patch('src.core.github_api.execute_github_graphql_query')
    @patch('src.core.github_api.load_cache')
    @patch('src.core.github_api.save_cache')
    def test_check_if_user_follows_viewer_true(self, mock_save, mock_load, mock_query):
        """Test checking if user follows viewer - true case."""
        from src.core.github_api import check_if_user_follows_viewer

        mock_load.return_value = {}
        mock_query.return_value = {
            'data': {
                'user': {
                    'isFollowingViewer': True
                }
            }
        }

        result = check_if_user_follows_viewer('follower')

        assert result is True

    @patch('src.core.github_api.execute_github_graphql_query')
    @patch('src.core.github_api.load_cache')
    @patch('src.core.github_api.save_cache')
    def test_check_if_user_follows_viewer_false(self, mock_save, mock_load, mock_query):
        """Test checking if user follows viewer - false case."""
        from src.core.github_api import check_if_user_follows_viewer

        mock_load.return_value = {}
        mock_query.return_value = {
            'data': {
                'user': {
                    'isFollowingViewer': False
                }
            }
        }

        result = check_if_user_follows_viewer('nonfollower')

        assert result is False

    @patch('src.core.github_api.execute_github_graphql_query')
    @patch('src.core.github_api.load_cache')
    def test_check_if_user_follows_viewer_not_found(self, mock_load, mock_query):
        """Test checking if non-existent user follows viewer."""
        from src.core.github_api import check_if_user_follows_viewer

        mock_load.return_value = {}
        mock_query.return_value = {
            'data': {
                'user': None
            }
        }

        with pytest.raises(Exception) as exc_info:
            check_if_user_follows_viewer('nonexistent')

        assert 'not found' in str(exc_info.value).lower()
