"""
Unit tests for API routes.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIndexRoute:
    """Tests for the index route."""

    def test_index_returns_html(self, client):
        """Test that index returns HTML page."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data


class TestGetDataRoute:
    """Tests for the /get_data endpoint."""

    @patch('app.get_cached_followers')
    @patch('app.is_cache_stale')
    @patch('app.load_ignore_list')
    @patch('app.get_sync_status')
    def test_get_followers(self, mock_sync_status, mock_ignore, mock_stale, mock_cached, client):
        """Test getting followers."""
        mock_stale.return_value = False
        mock_ignore.return_value = set()
        mock_cached.return_value = [
            {'login': 'user1', 'followers': 100, 'following': 50},
            {'login': 'user2', 'followers': 200, 'following': 100}
        ]
        mock_sync_status.return_value = {
            'last_sync_at': '2024-01-01T00:00:00',
            'is_stale': False
        }

        response = client.get('/get_data?type=followers')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'followers' in data
        assert 'pagination' in data
        assert len(data['followers']) == 2

    @patch('app.get_cached_following')
    @patch('app.is_cache_stale')
    @patch('app.load_ignore_list')
    @patch('app.get_sync_status')
    def test_get_following(self, mock_sync_status, mock_ignore, mock_stale, mock_cached, client):
        """Test getting following."""
        mock_stale.return_value = False
        mock_ignore.return_value = set()
        mock_cached.return_value = [
            {'login': 'following1', 'followers': 100, 'following': 50}
        ]
        mock_sync_status.return_value = {'last_sync_at': '2024-01-01T00:00:00'}

        response = client.get('/get_data?type=following')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'following' in data

    @patch('app.get_cached_new_followers')
    @patch('app.is_cache_stale')
    @patch('app.load_ignore_list')
    def test_get_new_followers(self, mock_ignore, mock_stale, mock_cached, client):
        """Test getting new followers."""
        mock_stale.return_value = False
        mock_ignore.return_value = set()
        mock_cached.return_value = [
            {'login': 'newuser', 'followers': 50}
        ]

        response = client.get('/get_data?type=new_followers')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'new_followers' in data

    @patch('app.get_cached_unfollowers')
    @patch('app.is_cache_stale')
    @patch('app.load_ignore_list')
    def test_get_unfollowers(self, mock_ignore, mock_stale, mock_cached, client):
        """Test getting unfollowers."""
        mock_stale.return_value = False
        mock_ignore.return_value = set()
        mock_cached.return_value = [
            {'login': 'unfollower1', 'followers': 30}
        ]

        response = client.get('/get_data?type=unfollowers')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'unfollowers' in data

    @patch('app.get_cached_not_following_back')
    @patch('app.is_cache_stale')
    @patch('app.load_ignore_list')
    def test_get_not_following_back(self, mock_ignore, mock_stale, mock_cached, client):
        """Test getting users not following back."""
        mock_stale.return_value = False
        mock_ignore.return_value = set()
        mock_cached.return_value = [
            {'login': 'notfollowingback', 'followers': 100}
        ]

        response = client.get('/get_data?type=not_following_back')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'not_following_back' in data

    def test_get_data_invalid_type(self, client):
        """Test getting data with invalid type."""
        response = client.get('/get_data?type=invalid')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    @patch('app.get_cached_followers')
    @patch('app.is_cache_stale')
    @patch('app.load_ignore_list')
    @patch('app.get_sync_status')
    def test_get_data_with_pagination(self, mock_sync, mock_ignore, mock_stale, mock_cached, client):
        """Test pagination parameters."""
        mock_stale.return_value = False
        mock_ignore.return_value = set()
        mock_cached.return_value = [{'login': f'user{i}'} for i in range(100)]
        mock_sync.return_value = {'last_sync_at': '2024-01-01'}

        response = client.get('/get_data?type=followers&page=2&per_page=10')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['pagination']['page'] == 2
        assert data['pagination']['per_page'] == 10
        assert len(data['followers']) == 10

    @patch('app.get_cached_followers')
    @patch('app.is_cache_stale')
    @patch('app.load_ignore_list')
    @patch('app.get_sync_status')
    def test_get_data_with_search(self, mock_sync, mock_ignore, mock_stale, mock_cached, client):
        """Test search filtering."""
        mock_stale.return_value = False
        mock_ignore.return_value = set()
        mock_cached.return_value = [
            {'login': 'alice'},
            {'login': 'bob'},
            {'login': 'charlie'}
        ]
        mock_sync.return_value = {'last_sync_at': '2024-01-01'}

        response = client.get('/get_data?type=followers&search=ali')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['followers']) == 1
        assert data['followers'][0]['login'] == 'alice'

    @patch('app.get_cached_followers')
    @patch('app.is_cache_stale')
    @patch('app.load_ignore_list')
    @patch('app.get_sync_status')
    def test_ignore_list_filtering(self, mock_sync, mock_ignore, mock_stale, mock_cached, client):
        """Test that ignored users are filtered out."""
        mock_stale.return_value = False
        mock_ignore.return_value = {'ignoreduser'}
        mock_cached.return_value = [
            {'login': 'normaluser'},
            {'login': 'ignoreduser'}
        ]
        mock_sync.return_value = {'last_sync_at': '2024-01-01'}

        response = client.get('/get_data?type=followers')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['followers']) == 1
        assert data['followers'][0]['login'] == 'normaluser'


class TestFollowUnfollowRoutes:
    """Tests for follow/unfollow endpoints."""

    @patch('app.follow_user')
    @patch('app.log_action')
    @patch('app.record_follower_event')
    def test_follow_success(self, mock_event, mock_log, mock_follow, client):
        """Test successful follow."""
        mock_follow.return_value = (True, '')

        response = client.post('/follow/validuser')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    @patch('app.follow_user')
    @patch('app.log_action')
    def test_follow_failure(self, mock_log, mock_follow, client):
        """Test failed follow."""
        mock_follow.return_value = (False, 'User not found')

        response = client.post('/follow/nonexistent')

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] is False

    def test_follow_invalid_username(self, client):
        """Test following invalid username."""
        response = client.post('/follow/-invaliduser')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    @patch('app.unfollow_user')
    @patch('app.log_action')
    @patch('app.record_follower_event')
    def test_unfollow_success(self, mock_event, mock_log, mock_unfollow, client):
        """Test successful unfollow."""
        mock_unfollow.return_value = (True, '')

        response = client.post('/unfollow/validuser')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    @patch('app.unfollow_user')
    @patch('app.log_action')
    def test_unfollow_failure(self, mock_log, mock_unfollow, client):
        """Test failed unfollow."""
        mock_unfollow.return_value = (False, 'User not found')

        response = client.post('/unfollow/nonexistent')

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] is False


class TestBulkOperations:
    """Tests for bulk follow/unfollow endpoints."""

    @patch('app.bulk_follow_users')
    @patch('app.log_action')
    def test_bulk_follow(self, mock_log, mock_bulk, client):
        """Test bulk follow."""
        mock_bulk.return_value = {
            'user1': {'success': True, 'message': ''},
            'user2': {'success': True, 'message': ''}
        }

        response = client.post(
            '/bulk_follow',
            data=json.dumps({'usernames': ['user1', 'user2']}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['user1']['success'] is True

    def test_bulk_follow_dry_run(self, client):
        """Test bulk follow dry run."""
        response = client.post(
            '/bulk_follow',
            data=json.dumps({'usernames': ['user1', 'user2'], 'dry_run': True}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['dry_run'] is True
        assert 'user1' in data['would_follow']

    @patch('app.bulk_unfollow_users')
    @patch('app.log_action')
    def test_bulk_unfollow(self, mock_log, mock_bulk, client):
        """Test bulk unfollow."""
        mock_bulk.return_value = {
            'user1': {'success': True, 'message': ''}
        }

        response = client.post(
            '/bulk_unfollow',
            data=json.dumps({'usernames': ['user1']}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['user1']['success'] is True


class TestSyncEndpoints:
    """Tests for sync-related endpoints."""

    @patch('app.perform_sync')
    @patch('app.get_all_sync_status')
    def test_trigger_sync(self, mock_status, mock_sync, client):
        """Test manual sync trigger."""
        mock_sync.return_value = True
        mock_status.return_value = {
            'followers': {'last_sync_at': '2024-01-01'},
            'following': {'last_sync_at': '2024-01-01'}
        }

        response = client.post(
            '/api/sync',
            data=json.dumps({'type': 'all'}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_trigger_sync_invalid_type(self, client):
        """Test sync with invalid type."""
        response = client.post(
            '/api/sync',
            data=json.dumps({'type': 'invalid'}),
            content_type='application/json'
        )

        assert response.status_code == 400

    @patch('app.get_all_sync_status')
    def test_get_sync_status(self, mock_status, client):
        """Test getting sync status."""
        mock_status.return_value = {
            'followers': {'last_sync_at': '2024-01-01', 'is_stale': False},
            'following': {'last_sync_at': '2024-01-01', 'is_stale': False}
        }

        response = client.get('/api/sync/status')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'followers' in data
        assert 'following' in data


class TestIgnoreListEndpoints:
    """Tests for ignore list management endpoints."""

    @patch('app.load_ignore_list')
    def test_get_ignore_list(self, mock_load, client):
        """Test getting ignore list."""
        mock_load.return_value = {'user1', 'user2'}

        response = client.get('/api/ignore-list')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'ignore_list' in data

    @patch('app.add_to_ignore_list')
    def test_add_to_ignore_list(self, mock_add, client):
        """Test adding to ignore list."""
        mock_add.return_value = {'user1', 'newuser'}

        response = client.post(
            '/api/ignore-list',
            data=json.dumps({'username': 'newuser'}),
            content_type='application/json'
        )

        assert response.status_code == 200

    def test_add_to_ignore_list_empty_username(self, client):
        """Test adding empty username to ignore list."""
        response = client.post(
            '/api/ignore-list',
            data=json.dumps({'username': ''}),
            content_type='application/json'
        )

        assert response.status_code == 400

    @patch('app.remove_from_ignore_list')
    def test_remove_from_ignore_list(self, mock_remove, client):
        """Test removing from ignore list."""
        mock_remove.return_value = {'user1'}

        response = client.delete(
            '/api/ignore-list',
            data=json.dumps({'username': 'user2'}),
            content_type='application/json'
        )

        assert response.status_code == 200


class TestUserPreview:
    """Tests for user preview endpoint."""

    @patch('app.get_users_info')
    def test_user_preview_success(self, mock_info, client):
        """Test successful user preview."""
        mock_info.return_value = [{
            'login': 'testuser',
            'followers': 100,
            'following': 50,
            'bio': 'Test bio'
        }]

        response = client.get('/api/user/testuser/preview')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['login'] == 'testuser'
        assert 'avatar_url' in data
        assert 'profile_url' in data

    @patch('app.get_users_info')
    def test_user_preview_not_found(self, mock_info, client):
        """Test user preview for non-existent user."""
        mock_info.return_value = []

        response = client.get('/api/user/nonexistent/preview')

        assert response.status_code == 404

    def test_user_preview_invalid_username(self, client):
        """Test user preview with invalid username."""
        response = client.get('/api/user/-invalid/preview')

        assert response.status_code == 400


class TestCheckFollow:
    """Tests for check follow endpoint."""

    @patch('app.check_if_user_follows_viewer')
    def test_check_follow_true(self, mock_check, client):
        """Test check if user follows - true."""
        mock_check.return_value = True

        response = client.get('/check_follow?username=follower')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['follows_you'] is True

    @patch('app.check_if_user_follows_viewer')
    def test_check_follow_false(self, mock_check, client):
        """Test check if user follows - false."""
        mock_check.return_value = False

        response = client.get('/check_follow?username=nonfollower')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['follows_you'] is False

    def test_check_follow_no_username(self, client):
        """Test check follow without username."""
        response = client.get('/check_follow')

        assert response.status_code == 400


class TestGetAllUsernames:
    """Tests for get all usernames endpoint."""

    @patch('app.get_cached_followers')
    @patch('app.is_cache_stale')
    @patch('app.load_ignore_list')
    def test_get_all_usernames_followers(self, mock_ignore, mock_stale, mock_cached, client):
        """Test getting all follower usernames."""
        mock_stale.return_value = False
        mock_ignore.return_value = set()
        mock_cached.return_value = [
            {'login': 'user1'},
            {'login': 'user2'},
            {'login': 'user3'}
        ]

        response = client.get('/get_all_usernames?type=followers')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['usernames']) == 3
        assert data['count'] == 3

    def test_get_all_usernames_invalid_type(self, client):
        """Test getting usernames with invalid type."""
        response = client.get('/get_all_usernames?type=invalid')

        assert response.status_code == 400


class TestHelperFunctions:
    """Tests for helper functions in app.py."""

    def test_is_valid_github_username_valid(self):
        """Test valid GitHub usernames."""
        from app import _is_valid_github_username

        assert _is_valid_github_username('validuser') is True
        assert _is_valid_github_username('valid-user') is True
        assert _is_valid_github_username('user123') is True
        assert _is_valid_github_username('a') is True

    def test_is_valid_github_username_invalid(self):
        """Test invalid GitHub usernames."""
        from app import _is_valid_github_username

        assert _is_valid_github_username('') is False
        assert _is_valid_github_username(None) is False
        assert _is_valid_github_username('-startshyphen') is False
        assert _is_valid_github_username('a' * 40) is False  # Too long
        assert _is_valid_github_username('user@name') is False
        assert _is_valid_github_username('user.name') is False

    def test_paginate_list(self):
        """Test list pagination."""
        from app import paginate_list

        items = list(range(25))
        result = paginate_list(items, page=2, per_page=10)

        assert len(result['items']) == 10
        assert result['pagination']['page'] == 2
        assert result['pagination']['total'] == 25
        assert result['pagination']['total_pages'] == 3
        assert result['pagination']['has_next'] is True
        assert result['pagination']['has_prev'] is True

    def test_paginate_list_last_page(self):
        """Test pagination on last page."""
        from app import paginate_list

        items = list(range(25))
        result = paginate_list(items, page=3, per_page=10)

        assert len(result['items']) == 5
        assert result['pagination']['has_next'] is False
        assert result['pagination']['has_prev'] is True

    def test_filter_and_sort_search(self):
        """Test filter and sort with search."""
        from app import filter_and_sort

        items = [
            {'login': 'alice'},
            {'login': 'bob'},
            {'login': 'charlie'}
        ]

        result = filter_and_sort(items, search='ali')

        assert len(result) == 1
        assert result[0]['login'] == 'alice'

    def test_filter_and_sort_by_followers(self):
        """Test sorting by followers."""
        from app import filter_and_sort

        items = [
            {'login': 'user1', 'followers': 100},
            {'login': 'user2', 'followers': 50},
            {'login': 'user3', 'followers': 200}
        ]

        result = filter_and_sort(items, sort_by='followers', order='desc')

        assert result[0]['login'] == 'user3'
        assert result[1]['login'] == 'user1'
        assert result[2]['login'] == 'user2'
