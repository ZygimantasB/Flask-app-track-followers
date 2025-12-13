"""
Unit tests for database module.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDatabaseModels:
    """Tests for database model creation and basic operations."""

    def test_account_model_creation(self, db_session):
        """Test Account model creation."""
        from src.core.database import Account

        account = Account(
            username='testuser',
            token='test_token_123',
            is_active=True,
            is_default=True
        )
        db_session.add(account)
        db_session.commit()

        assert account.id is not None
        assert account.username == 'testuser'
        assert account.is_active is True
        assert account.is_default is True

    def test_account_repr(self, db_session):
        """Test Account string representation."""
        from src.core.database import Account

        account = Account(username='testuser', token='token')
        assert '<Account testuser>' in repr(account)

    def test_follower_history_model(self, db_session, test_account):
        """Test FollowerHistory model."""
        from src.core.database import FollowerHistory

        event = FollowerHistory(
            account_id=test_account.id,
            username='follower1',
            event_type='followed',
            follower_count_at_event=100,
            following_count_at_event=50
        )
        db_session.add(event)
        db_session.commit()

        assert event.id is not None
        assert event.username == 'follower1'
        assert event.event_type == 'followed'

    def test_follower_snapshot_model(self, db_session, test_account):
        """Test FollowerSnapshot model."""
        from src.core.database import FollowerSnapshot

        snapshot = FollowerSnapshot(
            account_id=test_account.id,
            snapshot_date=datetime.utcnow(),
            follower_count=100,
            following_count=50,
            new_followers=5,
            lost_followers=2
        )
        db_session.add(snapshot)
        db_session.commit()

        assert snapshot.id is not None
        assert snapshot.follower_count == 100

    def test_user_metadata_tags(self, db_session, test_account):
        """Test UserMetadata tags functionality."""
        from src.core.database import UserMetadata

        metadata = UserMetadata(
            account_id=test_account.id,
            username='someuser'
        )
        metadata.set_tags_list(['python', 'javascript', 'python'])  # Test dedup

        assert 'python' in metadata.get_tags_list()
        assert 'javascript' in metadata.get_tags_list()
        assert len(metadata.get_tags_list()) == 2  # Should be deduplicated

    def test_cached_follower_to_dict(self, db_session, test_account):
        """Test CachedFollower to_dict method."""
        from src.core.database import CachedFollower

        follower = CachedFollower(
            account_id=test_account.id,
            username='testfollower',
            follower_count=100,
            following_count=50,
            bio='Test bio',
            user_type='User'
        )
        db_session.add(follower)
        db_session.commit()

        data = follower.to_dict()

        assert data['login'] == 'testfollower'
        assert data['followers'] == 100
        assert data['following'] == 50
        assert data['bio'] == 'Test bio'

    def test_sync_status_is_stale(self, db_session, test_account):
        """Test SyncStatus staleness check."""
        from src.core.database import SyncStatus

        # Fresh status
        status = SyncStatus(
            account_id=test_account.id,
            sync_type='followers',
            last_sync_at=datetime.utcnow(),
            sync_interval_minutes=15
        )
        db_session.add(status)
        db_session.commit()

        assert status.is_stale() is False

        # Stale status
        status.last_sync_at = datetime.utcnow() - timedelta(minutes=20)
        assert status.is_stale() is True

    def test_sync_status_never_synced(self, db_session, test_account):
        """Test SyncStatus when never synced."""
        from src.core.database import SyncStatus

        status = SyncStatus(
            account_id=test_account.id,
            sync_type='followers',
            last_sync_at=None
        )

        assert status.is_stale() is True


class TestDatabaseHelperFunctions:
    """Tests for database helper functions."""

    def test_get_or_create_account_new(self, db_session):
        """Test creating a new account."""
        from src.core.database import get_or_create_account, Account

        # Patch the session to use our test session
        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            account_id = get_or_create_account('newuser', 'newtoken', is_default=True)

            assert account_id is not None

    def test_record_follower_event(self, db_session, test_account):
        """Test recording follower events."""
        from src.core.database import record_follower_event, FollowerHistory

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            record_follower_event(
                test_account.id,
                'newuser',
                'followed',
                follower_count=100,
                following_count=50
            )

            events = db_session.query(FollowerHistory).filter_by(
                account_id=test_account.id,
                username='newuser'
            ).all()

            assert len(events) == 1
            assert events[0].event_type == 'followed'

    def test_take_daily_snapshot_new(self, db_session, test_account):
        """Test taking a new daily snapshot."""
        from src.core.database import take_daily_snapshot, FollowerSnapshot

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            take_daily_snapshot(
                test_account.id,
                follower_count=100,
                following_count=50,
                new_followers=5,
                lost_followers=2
            )

            snapshots = db_session.query(FollowerSnapshot).filter_by(
                account_id=test_account.id
            ).all()

            assert len(snapshots) == 1
            assert snapshots[0].follower_count == 100

    def test_log_action(self, db_session, test_account):
        """Test logging actions."""
        from src.core.database import log_action, ActionLog

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            action_id = log_action(
                test_account.id,
                'follow',
                target_username='testuser',
                success=True
            )

            assert action_id is not None

            action = db_session.query(ActionLog).get(action_id)
            assert action.action_type == 'follow'
            assert action.success is True


class TestSyncFunctions:
    """Tests for sync-related functions."""

    def test_sync_followers_new(self, db_session, test_account, sample_followers):
        """Test syncing new followers."""
        from src.core.database import sync_followers, CachedFollower, update_sync_status

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            with patch('src.core.database.update_sync_status'):
                result = sync_followers(test_account.id, sample_followers)

                assert result['total'] == 3
                assert len(result['added']) == 3
                assert len(result['removed']) == 0

    def test_sync_followers_with_removal(self, db_session, test_account):
        """Test syncing followers with removals."""
        from src.core.database import sync_followers, CachedFollower

        # Add existing follower
        existing = CachedFollower(
            account_id=test_account.id,
            username='old_follower',
            is_current=True
        )
        db_session.add(existing)
        db_session.commit()

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            with patch('src.core.database.update_sync_status'):
                # Sync with new followers, old one not included
                result = sync_followers(test_account.id, [{'login': 'new_follower'}])

                assert 'old_follower' in result['removed']
                assert 'new_follower' in result['added']

    def test_sync_following(self, db_session, test_account, sample_following):
        """Test syncing following list."""
        from src.core.database import sync_following

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            with patch('src.core.database.update_sync_status'):
                result = sync_following(test_account.id, sample_following)

                assert result['total'] == 2
                assert len(result['added']) == 2

    def test_get_cached_followers(self, db_session, test_account):
        """Test getting cached followers."""
        from src.core.database import get_cached_followers, CachedFollower

        # Add test followers
        for i in range(3):
            follower = CachedFollower(
                account_id=test_account.id,
                username=f'follower{i}',
                is_current=True
            )
            db_session.add(follower)

        # Add inactive follower
        inactive = CachedFollower(
            account_id=test_account.id,
            username='inactive',
            is_current=False
        )
        db_session.add(inactive)
        db_session.commit()

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            result = get_cached_followers(test_account.id, include_inactive=False)
            assert len(result) == 3

            result_all = get_cached_followers(test_account.id, include_inactive=True)
            assert len(result_all) == 4

    def test_get_cached_not_following_back(self, db_session, test_account):
        """Test getting users not following back."""
        from src.core.database import (
            get_cached_not_following_back,
            CachedFollower,
            CachedFollowing
        )

        # User we follow who follows us back
        follower = CachedFollower(
            account_id=test_account.id,
            username='mutual',
            is_current=True
        )
        following_mutual = CachedFollowing(
            account_id=test_account.id,
            username='mutual',
            is_current=True
        )

        # User we follow who doesn't follow back
        following_not_back = CachedFollowing(
            account_id=test_account.id,
            username='not_following_back',
            is_current=True
        )

        db_session.add_all([follower, following_mutual, following_not_back])
        db_session.commit()

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            result = get_cached_not_following_back(test_account.id)

            usernames = [u['login'] for u in result]
            assert 'not_following_back' in usernames
            assert 'mutual' not in usernames

    def test_get_cached_new_followers(self, db_session, test_account):
        """Test getting new followers."""
        from src.core.database import get_cached_new_followers, CachedFollower

        # Recent follower
        recent = CachedFollower(
            account_id=test_account.id,
            username='recent',
            is_current=True,
            first_seen_at=datetime.utcnow()
        )

        # Old follower
        old = CachedFollower(
            account_id=test_account.id,
            username='old',
            is_current=True,
            first_seen_at=datetime.utcnow() - timedelta(days=10)
        )

        db_session.add_all([recent, old])
        db_session.commit()

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            result = get_cached_new_followers(test_account.id, days=3)

            usernames = [u['login'] for u in result]
            assert 'recent' in usernames
            assert 'old' not in usernames

    def test_get_cached_unfollowers(self, db_session, test_account):
        """Test getting unfollowers."""
        from src.core.database import get_cached_unfollowers, CachedFollower

        # Recent unfollower
        recent_unfollower = CachedFollower(
            account_id=test_account.id,
            username='recent_unfollower',
            is_current=False,
            last_seen_at=datetime.utcnow() - timedelta(days=1)
        )

        # Old unfollower
        old_unfollower = CachedFollower(
            account_id=test_account.id,
            username='old_unfollower',
            is_current=False,
            last_seen_at=datetime.utcnow() - timedelta(days=60)
        )

        db_session.add_all([recent_unfollower, old_unfollower])
        db_session.commit()

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            result = get_cached_unfollowers(test_account.id, days=30)

            usernames = [u['login'] for u in result]
            assert 'recent_unfollower' in usernames
            assert 'old_unfollower' not in usernames


class TestAnalytics:
    """Tests for analytics functions."""

    def test_get_analytics(self, db_session, test_account):
        """Test getting analytics data."""
        from src.core.database import get_analytics, FollowerSnapshot, FollowerHistory

        # Add snapshots
        for i in range(5):
            snapshot = FollowerSnapshot(
                account_id=test_account.id,
                snapshot_date=datetime.utcnow() - timedelta(days=i),
                follower_count=100 + i * 10,
                following_count=50,
                new_followers=5,
                lost_followers=2
            )
            db_session.add(snapshot)

        # Add events
        event = FollowerHistory(
            account_id=test_account.id,
            username='testuser',
            event_type='followed'
        )
        db_session.add(event)
        db_session.commit()

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            result = get_analytics(test_account.id, days=30)

            assert 'snapshots' in result
            assert 'events' in result
            assert 'summary' in result
            assert len(result['snapshots']) == 5


class TestSyncStatus:
    """Tests for sync status functions."""

    def test_get_sync_status_none(self, db_session, test_account):
        """Test getting sync status when none exists."""
        from src.core.database import get_sync_status

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            result = get_sync_status(test_account.id, 'followers')

            assert result['is_stale'] is True
            assert result['last_sync_at'] is None

    def test_update_sync_status(self, db_session, test_account):
        """Test updating sync status."""
        from src.core.database import update_sync_status, SyncStatus

        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            update_sync_status(
                test_account.id,
                'followers',
                success=True,
                items_synced=100,
                items_added=5,
                items_removed=2
            )

            status = db_session.query(SyncStatus).filter_by(
                account_id=test_account.id,
                sync_type='followers'
            ).first()

            assert status is not None
            assert status.items_synced == 100
            assert status.last_sync_success is True

    def test_is_cache_stale(self, db_session, test_account):
        """Test cache staleness check."""
        from src.core.database import is_cache_stale, SyncStatus

        # No status = stale
        with patch('src.core.database.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            assert is_cache_stale(test_account.id, 'followers') is True

            # Add fresh status
            status = SyncStatus(
                account_id=test_account.id,
                sync_type='followers',
                last_sync_at=datetime.utcnow(),
                sync_interval_minutes=15
            )
            db_session.add(status)
            db_session.commit()

            assert is_cache_stale(test_account.id, 'followers') is False
