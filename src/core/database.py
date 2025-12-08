"""
Database module for GitHub Followers Tracker.
Uses SQLite for persistence with SQLAlchemy ORM.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, Index, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = os.getenv('GFT_DATABASE_PATH', 'data/github_tracker.db')
DATABASE_URL = f'sqlite:///{DB_PATH}'

# Create engine with optimizations
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={'check_same_thread': False}
)

# Enable WAL mode for better concurrent access
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
    cursor.close()

# Session factory
SessionFactory = sessionmaker(bind=engine)
Session = scoped_session(SessionFactory)

Base = declarative_base()


class Account(Base):
    """GitHub account configuration for multi-account support."""
    __tablename__ = 'accounts'

    id = Column(Integer, primary_key=True)
    username = Column(String(39), unique=True, nullable=False)
    token = Column(String(255), nullable=False)  # Encrypted in production
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    followers_history = relationship('FollowerHistory', back_populates='account', cascade='all, delete-orphan')
    snapshots = relationship('FollowerSnapshot', back_populates='account', cascade='all, delete-orphan')
    user_metadata = relationship('UserMetadata', back_populates='account', cascade='all, delete-orphan')
    webhooks = relationship('Webhook', back_populates='account', cascade='all, delete-orphan')
    schedule_configs = relationship('ScheduleConfig', back_populates='account', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Account {self.username}>'


class FollowerHistory(Base):
    """Track follow/unfollow events over time."""
    __tablename__ = 'follower_history'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    username = Column(String(39), nullable=False)
    event_type = Column(String(20), nullable=False)  # 'followed', 'unfollowed', 'you_followed', 'you_unfollowed'
    event_time = Column(DateTime, default=datetime.utcnow)

    # Additional context
    follower_count_at_event = Column(Integer)
    following_count_at_event = Column(Integer)

    account = relationship('Account', back_populates='followers_history')

    __table_args__ = (
        Index('idx_follower_history_account_time', 'account_id', 'event_time'),
        Index('idx_follower_history_username', 'username'),
    )

    def __repr__(self):
        return f'<FollowerHistory {self.username} {self.event_type}>'


class FollowerSnapshot(Base):
    """Daily snapshots of follower/following counts for analytics."""
    __tablename__ = 'follower_snapshots'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    snapshot_date = Column(DateTime, nullable=False)
    follower_count = Column(Integer, nullable=False)
    following_count = Column(Integer, nullable=False)
    new_followers = Column(Integer, default=0)
    lost_followers = Column(Integer, default=0)
    new_following = Column(Integer, default=0)
    removed_following = Column(Integer, default=0)

    account = relationship('Account', back_populates='snapshots')

    __table_args__ = (
        Index('idx_snapshot_account_date', 'account_id', 'snapshot_date', unique=True),
    )

    def __repr__(self):
        return f'<FollowerSnapshot {self.snapshot_date} followers={self.follower_count}>'


class UserMetadata(Base):
    """Store metadata about users (notes, tags, whitelist status, etc.)."""
    __tablename__ = 'user_metadata'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    username = Column(String(39), nullable=False)

    # User management features
    is_whitelisted = Column(Boolean, default=False)
    is_ignored = Column(Boolean, default=False)
    notes = Column(Text)
    tags = Column(String(500))  # Comma-separated tags

    # Follow-back tracking
    followed_at = Column(DateTime)  # When we followed them
    follow_back_deadline = Column(DateTime)  # Auto-unfollow if not followed back by this date

    # Cached user info
    avatar_url = Column(String(500))
    bio = Column(Text)
    follower_count = Column(Integer)
    following_count = Column(Integer)
    public_repos = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow)

    account = relationship('Account', back_populates='user_metadata')

    __table_args__ = (
        Index('idx_user_metadata_account_username', 'account_id', 'username', unique=True),
        Index('idx_user_metadata_whitelisted', 'account_id', 'is_whitelisted'),
        Index('idx_user_metadata_deadline', 'account_id', 'follow_back_deadline'),
    )

    def __repr__(self):
        return f'<UserMetadata {self.username}>'

    def get_tags_list(self) -> List[str]:
        """Get tags as a list."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    def set_tags_list(self, tags: List[str]):
        """Set tags from a list."""
        self.tags = ','.join(sorted(set(t.strip().lower() for t in tags if t.strip())))


class Webhook(Base):
    """Webhook configurations for notifications."""
    __tablename__ = 'webhooks'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    secret = Column(String(255))  # Optional HMAC secret
    is_active = Column(Boolean, default=True)

    # Event filters (comma-separated)
    events = Column(String(500), default='all')  # 'all', 'follower_gained', 'follower_lost', 'milestone', etc.

    # Stats
    last_triggered = Column(DateTime)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship('Account', back_populates='webhooks')

    def __repr__(self):
        return f'<Webhook {self.name}>'

    def get_events_list(self) -> List[str]:
        """Get events as a list."""
        if not self.events or self.events == 'all':
            return ['all']
        return [e.strip() for e in self.events.split(',') if e.strip()]


class ScheduleConfig(Base):
    """Configurable scheduling for automated tasks."""
    __tablename__ = 'schedule_configs'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    task_name = Column(String(50), nullable=False)  # 'daily_follow', 'monthly_unfollow', etc.
    is_enabled = Column(Boolean, default=True)

    # Cron-like scheduling
    hour = Column(Integer, default=6)
    minute = Column(Integer, default=0)
    day_of_month = Column(Integer)  # For monthly tasks
    day_of_week = Column(Integer)   # 0=Monday, 6=Sunday

    # Task parameters
    parameters = Column(Text)  # JSON string for task-specific params

    # Dry run mode
    dry_run = Column(Boolean, default=False)

    last_run = Column(DateTime)
    next_run = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship('Account', back_populates='schedule_configs')

    __table_args__ = (
        Index('idx_schedule_account_task', 'account_id', 'task_name', unique=True),
    )

    def __repr__(self):
        return f'<ScheduleConfig {self.task_name}>'


class ActionLog(Base):
    """Log of all actions for undo functionality."""
    __tablename__ = 'action_logs'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    action_type = Column(String(50), nullable=False)  # 'follow', 'unfollow', 'bulk_follow', 'bulk_unfollow'
    target_username = Column(String(39))
    target_usernames = Column(Text)  # JSON array for bulk actions

    # For undo
    is_undone = Column(Boolean, default=False)
    undone_at = Column(DateTime)

    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_action_log_account_time', 'account_id', 'created_at'),
    )

    def __repr__(self):
        return f'<ActionLog {self.action_type} {self.target_username}>'


class NotificationConfig(Base):
    """Email and notification settings."""
    __tablename__ = 'notification_configs'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)

    # Email settings
    email_enabled = Column(Boolean, default=False)
    email_address = Column(String(255))
    smtp_host = Column(String(255))
    smtp_port = Column(Integer, default=587)
    smtp_username = Column(String(255))
    smtp_password = Column(String(255))  # Should be encrypted
    smtp_use_tls = Column(Boolean, default=True)

    # Notification preferences
    notify_on_follow = Column(Boolean, default=True)
    notify_on_unfollow = Column(Boolean, default=True)
    notify_on_milestone = Column(Boolean, default=True)

    # Digest settings
    daily_digest_enabled = Column(Boolean, default=False)
    daily_digest_hour = Column(Integer, default=9)
    weekly_digest_enabled = Column(Boolean, default=False)
    weekly_digest_day = Column(Integer, default=0)  # Monday

    # Milestone thresholds (JSON array)
    milestone_thresholds = Column(Text, default='[100, 500, 1000, 5000, 10000]')

    __table_args__ = (
        Index('idx_notification_account', 'account_id', unique=True),
    )


class Milestone(Base):
    """Track reached milestones."""
    __tablename__ = 'milestones'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    milestone_type = Column(String(50), nullable=False)  # 'followers', 'following'
    threshold = Column(Integer, nullable=False)
    reached_at = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)

    __table_args__ = (
        Index('idx_milestone_account_type', 'account_id', 'milestone_type', 'threshold', unique=True),
    )


class CachedFollower(Base):
    """Cache of current followers - synced periodically from GitHub API."""
    __tablename__ = 'cached_followers'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    username = Column(String(39), nullable=False)

    # Cached user info
    avatar_url = Column(String(500))
    bio = Column(Text)
    follower_count = Column(Integer)
    following_count = Column(Integer)
    public_repos = Column(Integer)
    user_type = Column(String(20), default='User')  # 'User' or 'Organization'

    # Tracking
    first_seen_at = Column(DateTime, default=datetime.utcnow)  # When they first followed
    last_seen_at = Column(DateTime, default=datetime.utcnow)   # Last sync where they were present
    is_current = Column(Boolean, default=True)  # False if they unfollowed

    __table_args__ = (
        Index('idx_cached_followers_account_username', 'account_id', 'username', unique=True),
        Index('idx_cached_followers_current', 'account_id', 'is_current'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'login': self.username,
            'avatar_url': self.avatar_url or f"https://github.com/{self.username}.png?size=40",
            'bio': self.bio,
            'followers': self.follower_count or 0,
            'following': self.following_count or 0,
            'public_repos': self.public_repos or 0,
            'type': self.user_type,
            'first_seen_at': self.first_seen_at.isoformat() if self.first_seen_at else None,
        }


class CachedFollowing(Base):
    """Cache of users we are following - synced periodically from GitHub API."""
    __tablename__ = 'cached_following'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    username = Column(String(39), nullable=False)

    # Cached user info
    avatar_url = Column(String(500))
    bio = Column(Text)
    follower_count = Column(Integer)
    following_count = Column(Integer)
    public_repos = Column(Integer)
    user_type = Column(String(20), default='User')

    # Tracking
    followed_at = Column(DateTime, default=datetime.utcnow)  # When we followed them
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    is_current = Column(Boolean, default=True)  # False if we unfollowed

    __table_args__ = (
        Index('idx_cached_following_account_username', 'account_id', 'username', unique=True),
        Index('idx_cached_following_current', 'account_id', 'is_current'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'login': self.username,
            'avatar_url': self.avatar_url or f"https://github.com/{self.username}.png?size=40",
            'bio': self.bio,
            'followers': self.follower_count or 0,
            'following': self.following_count or 0,
            'public_repos': self.public_repos or 0,
            'type': self.user_type,
            'followed_at': self.followed_at.isoformat() if self.followed_at else None,
        }


class SyncStatus(Base):
    """Track sync status for each data type."""
    __tablename__ = 'sync_status'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    sync_type = Column(String(50), nullable=False)  # 'followers', 'following', 'full'

    last_sync_at = Column(DateTime)
    last_sync_success = Column(Boolean, default=True)
    last_sync_error = Column(Text)
    items_synced = Column(Integer, default=0)
    items_added = Column(Integer, default=0)
    items_removed = Column(Integer, default=0)

    # Sync settings
    sync_interval_minutes = Column(Integer, default=15)
    auto_sync_enabled = Column(Boolean, default=True)

    __table_args__ = (
        Index('idx_sync_status_account_type', 'account_id', 'sync_type', unique=True),
    )

    def is_stale(self) -> bool:
        """Check if data needs to be synced."""
        if not self.last_sync_at:
            return True
        age = datetime.utcnow() - self.last_sync_at
        return age > timedelta(minutes=self.sync_interval_minutes)

    def next_sync_at(self) -> Optional[datetime]:
        """Calculate when next sync should occur."""
        if not self.last_sync_at:
            return datetime.utcnow()
        return self.last_sync_at + timedelta(minutes=self.sync_interval_minutes)


# Database helper functions
@contextmanager
def get_session():
    """Context manager for database sessions."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def init_db():
    """Initialize the database schema."""
    logger.info(f"Initializing database at {DB_PATH}")
    Base.metadata.create_all(engine)
    logger.info("Database initialized successfully")


def get_or_create_account(username: str, token: str, is_default: bool = False) -> int:
    """Get existing account or create new one. Returns the account ID."""
    with get_session() as session:
        account = session.query(Account).filter_by(username=username).first()
        if not account:
            account = Account(username=username, token=token, is_default=is_default)
            session.add(account)
            session.flush()
            logger.info(f"Created new account: {username}")
        else:
            account.token = token
            if is_default:
                # Unset other defaults
                session.query(Account).filter(Account.id != account.id).update({'is_default': False})
                account.is_default = True
        # Return the ID before session closes to avoid DetachedInstanceError
        account_id = account.id
        return account_id


def record_follower_event(account_id: int, username: str, event_type: str,
                          follower_count: int = None, following_count: int = None):
    """Record a follow/unfollow event."""
    with get_session() as session:
        event = FollowerHistory(
            account_id=account_id,
            username=username,
            event_type=event_type,
            follower_count_at_event=follower_count,
            following_count_at_event=following_count
        )
        session.add(event)
        logger.debug(f"Recorded event: {username} {event_type}")


def take_daily_snapshot(account_id: int, follower_count: int, following_count: int,
                        new_followers: int = 0, lost_followers: int = 0,
                        new_following: int = 0, removed_following: int = 0):
    """Take a daily snapshot of follower/following counts."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    with get_session() as session:
        # Check if snapshot exists for today
        existing = session.query(FollowerSnapshot).filter_by(
            account_id=account_id,
            snapshot_date=today
        ).first()

        if existing:
            existing.follower_count = follower_count
            existing.following_count = following_count
            existing.new_followers = new_followers
            existing.lost_followers = lost_followers
            existing.new_following = new_following
            existing.removed_following = removed_following
        else:
            snapshot = FollowerSnapshot(
                account_id=account_id,
                snapshot_date=today,
                follower_count=follower_count,
                following_count=following_count,
                new_followers=new_followers,
                lost_followers=lost_followers,
                new_following=new_following,
                removed_following=removed_following
            )
            session.add(snapshot)

        logger.info(f"Snapshot taken: {follower_count} followers, {following_count} following")


def get_analytics(account_id: int, days: int = 30) -> Dict[str, Any]:
    """Get analytics data for the specified period."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        snapshots = session.query(FollowerSnapshot).filter(
            FollowerSnapshot.account_id == account_id,
            FollowerSnapshot.snapshot_date >= cutoff
        ).order_by(FollowerSnapshot.snapshot_date).all()

        events = session.query(FollowerHistory).filter(
            FollowerHistory.account_id == account_id,
            FollowerHistory.event_time >= cutoff
        ).order_by(FollowerHistory.event_time).all()

        # Calculate statistics
        if snapshots:
            first = snapshots[0]
            last = snapshots[-1]
            growth = last.follower_count - first.follower_count
            growth_rate = (growth / first.follower_count * 100) if first.follower_count > 0 else 0
        else:
            growth = 0
            growth_rate = 0

        return {
            'period_days': days,
            'snapshots': [
                {
                    'date': s.snapshot_date.isoformat(),
                    'followers': s.follower_count,
                    'following': s.following_count,
                    'new_followers': s.new_followers,
                    'lost_followers': s.lost_followers
                }
                for s in snapshots
            ],
            'events': [
                {
                    'username': e.username,
                    'type': e.event_type,
                    'time': e.event_time.isoformat()
                }
                for e in events
            ],
            'summary': {
                'total_growth': growth,
                'growth_rate_percent': round(growth_rate, 2),
                'total_gained': sum(s.new_followers for s in snapshots),
                'total_lost': sum(s.lost_followers for s in snapshots)
            }
        }


def log_action(account_id: int, action_type: str, target_username: str = None,
               target_usernames: List[str] = None, success: bool = True,
               error_message: str = None) -> int:
    """Log an action for undo functionality."""
    import json

    with get_session() as session:
        action = ActionLog(
            account_id=account_id,
            action_type=action_type,
            target_username=target_username,
            target_usernames=json.dumps(target_usernames) if target_usernames else None,
            success=success,
            error_message=error_message
        )
        session.add(action)
        session.flush()
        return action.id


def get_recent_actions(account_id: int, limit: int = 50) -> List[Dict]:
    """Get recent actions for undo UI."""
    import json

    with get_session() as session:
        actions = session.query(ActionLog).filter_by(
            account_id=account_id,
            success=True,
            is_undone=False
        ).order_by(ActionLog.created_at.desc()).limit(limit).all()

        return [
            {
                'id': a.id,
                'type': a.action_type,
                'target': a.target_username or json.loads(a.target_usernames or '[]'),
                'time': a.created_at.isoformat(),
                'can_undo': not a.is_undone
            }
            for a in actions
        ]


# ============== SYNC FUNCTIONS ==============

def get_sync_status(account_id: int, sync_type: str) -> Dict[str, Any]:
    """Get the sync status for a specific type."""
    with get_session() as session:
        status = session.query(SyncStatus).filter_by(
            account_id=account_id,
            sync_type=sync_type
        ).first()

        if not status:
            return {
                'last_sync_at': None,
                'is_stale': True,
                'next_sync_at': datetime.utcnow().isoformat(),
                'items_synced': 0,
                'auto_sync_enabled': True
            }

        return {
            'last_sync_at': status.last_sync_at.isoformat() if status.last_sync_at else None,
            'is_stale': status.is_stale(),
            'next_sync_at': status.next_sync_at().isoformat() if status.next_sync_at() else None,
            'items_synced': status.items_synced,
            'items_added': status.items_added,
            'items_removed': status.items_removed,
            'last_sync_success': status.last_sync_success,
            'last_sync_error': status.last_sync_error,
            'auto_sync_enabled': status.auto_sync_enabled
        }


def update_sync_status(account_id: int, sync_type: str, success: bool,
                       items_synced: int = 0, items_added: int = 0,
                       items_removed: int = 0, error: str = None):
    """Update the sync status after a sync operation."""
    with get_session() as session:
        status = session.query(SyncStatus).filter_by(
            account_id=account_id,
            sync_type=sync_type
        ).first()

        if not status:
            status = SyncStatus(
                account_id=account_id,
                sync_type=sync_type
            )
            session.add(status)

        status.last_sync_at = datetime.utcnow()
        status.last_sync_success = success
        status.last_sync_error = error
        status.items_synced = items_synced
        status.items_added = items_added
        status.items_removed = items_removed


def sync_followers(account_id: int, followers_data: List[Dict]) -> Dict[str, Any]:
    """
    Sync followers from GitHub API to database cache.
    Returns stats about the sync operation.
    """
    now = datetime.utcnow()
    current_usernames = {f.get('login', f) if isinstance(f, dict) else f for f in followers_data}

    with get_session() as session:
        # Get existing cached followers
        existing = {f.username: f for f in session.query(CachedFollower).filter_by(
            account_id=account_id
        ).all()}

        existing_current = {u for u, f in existing.items() if f.is_current}

        added = []
        removed = []
        updated = 0

        # Process new/updated followers
        for f_data in followers_data:
            if isinstance(f_data, str):
                username = f_data
                user_info = {}
            else:
                username = f_data.get('login', '')
                user_info = f_data

            if not username:
                continue

            if username in existing:
                # Update existing record
                cached = existing[username]
                cached.is_current = True
                cached.last_seen_at = now
                # Update user info if provided
                if user_info.get('followers') is not None:
                    cached.follower_count = user_info.get('followers')
                if user_info.get('following') is not None:
                    cached.following_count = user_info.get('following')
                if user_info.get('bio'):
                    cached.bio = user_info.get('bio')
                if user_info.get('public_repos') is not None:
                    cached.public_repos = user_info.get('public_repos')
                if user_info.get('type'):
                    cached.user_type = user_info.get('type')
                updated += 1
            else:
                # New follower
                cached = CachedFollower(
                    account_id=account_id,
                    username=username,
                    avatar_url=user_info.get('avatar_url'),
                    bio=user_info.get('bio'),
                    follower_count=user_info.get('followers'),
                    following_count=user_info.get('following'),
                    public_repos=user_info.get('public_repos'),
                    user_type=user_info.get('type', 'User'),
                    first_seen_at=now,
                    last_seen_at=now,
                    is_current=True
                )
                session.add(cached)
                added.append(username)

        # Mark unfollowers
        for username in existing_current - current_usernames:
            existing[username].is_current = False
            removed.append(username)

        # Record events for new followers and unfollowers
        for username in added:
            event = FollowerHistory(
                account_id=account_id,
                username=username,
                event_type='followed',
                follower_count_at_event=len(current_usernames)
            )
            session.add(event)

        for username in removed:
            event = FollowerHistory(
                account_id=account_id,
                username=username,
                event_type='unfollowed',
                follower_count_at_event=len(current_usernames)
            )
            session.add(event)

    # Update sync status
    update_sync_status(
        account_id, 'followers', True,
        items_synced=len(current_usernames),
        items_added=len(added),
        items_removed=len(removed)
    )

    logger.info(f"Synced {len(current_usernames)} followers: +{len(added)}, -{len(removed)}")

    return {
        'total': len(current_usernames),
        'added': added,
        'removed': removed,
        'updated': updated
    }


def sync_following(account_id: int, following_data: List[Dict]) -> Dict[str, Any]:
    """
    Sync following list from GitHub API to database cache.
    Returns stats about the sync operation.
    """
    now = datetime.utcnow()
    current_usernames = {f.get('login', f) if isinstance(f, dict) else f for f in following_data}

    with get_session() as session:
        # Get existing cached following
        existing = {f.username: f for f in session.query(CachedFollowing).filter_by(
            account_id=account_id
        ).all()}

        existing_current = {u for u, f in existing.items() if f.is_current}

        added = []
        removed = []
        updated = 0

        # Process new/updated following
        for f_data in following_data:
            if isinstance(f_data, str):
                username = f_data
                user_info = {}
            else:
                username = f_data.get('login', '')
                user_info = f_data

            if not username:
                continue

            if username in existing:
                # Update existing record
                cached = existing[username]
                cached.is_current = True
                cached.last_seen_at = now
                if user_info.get('followers') is not None:
                    cached.follower_count = user_info.get('followers')
                if user_info.get('following') is not None:
                    cached.following_count = user_info.get('following')
                if user_info.get('bio'):
                    cached.bio = user_info.get('bio')
                if user_info.get('public_repos') is not None:
                    cached.public_repos = user_info.get('public_repos')
                if user_info.get('type'):
                    cached.user_type = user_info.get('type')
                updated += 1
            else:
                # New following
                cached = CachedFollowing(
                    account_id=account_id,
                    username=username,
                    avatar_url=user_info.get('avatar_url'),
                    bio=user_info.get('bio'),
                    follower_count=user_info.get('followers'),
                    following_count=user_info.get('following'),
                    public_repos=user_info.get('public_repos'),
                    user_type=user_info.get('type', 'User'),
                    followed_at=now,
                    last_seen_at=now,
                    is_current=True
                )
                session.add(cached)
                added.append(username)

        # Mark unfollowed users
        for username in existing_current - current_usernames:
            existing[username].is_current = False
            removed.append(username)

    # Update sync status
    update_sync_status(
        account_id, 'following', True,
        items_synced=len(current_usernames),
        items_added=len(added),
        items_removed=len(removed)
    )

    logger.info(f"Synced {len(current_usernames)} following: +{len(added)}, -{len(removed)}")

    return {
        'total': len(current_usernames),
        'added': added,
        'removed': removed,
        'updated': updated
    }


def get_cached_followers(account_id: int, include_inactive: bool = False) -> List[Dict]:
    """Get followers from cache."""
    with get_session() as session:
        query = session.query(CachedFollower).filter_by(account_id=account_id)
        if not include_inactive:
            query = query.filter_by(is_current=True)

        return [f.to_dict() for f in query.order_by(CachedFollower.username).all()]


def get_cached_following(account_id: int, include_inactive: bool = False) -> List[Dict]:
    """Get following from cache."""
    with get_session() as session:
        query = session.query(CachedFollowing).filter_by(account_id=account_id)
        if not include_inactive:
            query = query.filter_by(is_current=True)

        return [f.to_dict() for f in query.order_by(CachedFollowing.username).all()]


def get_cached_new_followers(account_id: int, days: int = 3) -> List[Dict]:
    """Get followers who started following within the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        followers = session.query(CachedFollower).filter(
            CachedFollower.account_id == account_id,
            CachedFollower.is_current == True,
            CachedFollower.first_seen_at >= cutoff
        ).order_by(CachedFollower.first_seen_at.desc()).all()

        return [f.to_dict() for f in followers]


def get_cached_unfollowers(account_id: int, days: int = 30) -> List[Dict]:
    """Get users who unfollowed within the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        unfollowers = session.query(CachedFollower).filter(
            CachedFollower.account_id == account_id,
            CachedFollower.is_current == False,
            CachedFollower.last_seen_at >= cutoff
        ).order_by(CachedFollower.last_seen_at.desc()).all()

        return [f.to_dict() for f in unfollowers]


def get_cached_not_following_back(account_id: int) -> List[Dict]:
    """Get users we follow who don't follow us back (from cache)."""
    with get_session() as session:
        # Get current followers usernames
        follower_usernames = {f.username.lower() for f in session.query(CachedFollower).filter_by(
            account_id=account_id,
            is_current=True
        ).all()}

        # Get current following who are not in followers
        not_following_back = session.query(CachedFollowing).filter(
            CachedFollowing.account_id == account_id,
            CachedFollowing.is_current == True
        ).all()

        return [
            f.to_dict() for f in not_following_back
            if f.username.lower() not in follower_usernames
        ]


def is_cache_stale(account_id: int, sync_type: str) -> bool:
    """Check if cache needs to be refreshed."""
    with get_session() as session:
        status = session.query(SyncStatus).filter_by(
            account_id=account_id,
            sync_type=sync_type
        ).first()

        if not status or not status.last_sync_at:
            return True

        return status.is_stale()


def get_all_sync_status(account_id: int) -> Dict[str, Any]:
    """Get sync status for all types."""
    return {
        'followers': get_sync_status(account_id, 'followers'),
        'following': get_sync_status(account_id, 'following'),
    }
