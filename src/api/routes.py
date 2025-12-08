"""
Extended API routes for GitHub Followers Tracker.
Includes analytics, webhooks, scheduling, export, and multi-account support.
"""
import json
import csv
import io
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify, Response, g
from typing import Optional

logger = logging.getLogger(__name__)

api = Blueprint('api', __name__, url_prefix='/api')


def get_current_account_id() -> int:
    """Get the current account ID from request or default."""
    from src.core.database import get_session, Account

    # Check if account_id is specified in request
    account_id = request.args.get('account_id') or request.json.get('account_id') if request.is_json else None

    if account_id:
        return int(account_id)

    # Get default account
    with get_session() as session:
        account = session.query(Account).filter_by(is_default=True).first()
        if account:
            return account.id

        # If no default, get first account
        account = session.query(Account).first()
        if account:
            return account.id

    return None


def require_account(f):
    """Decorator to require a valid account."""
    @wraps(f)
    def decorated(*args, **kwargs):
        account_id = get_current_account_id()
        if not account_id:
            return jsonify({'error': 'No account configured'}), 400
        g.account_id = account_id
        return f(*args, **kwargs)
    return decorated


# ============== Analytics Routes ==============

@api.route('/analytics')
@require_account
def get_analytics():
    """Get analytics data."""
    from src.core.database import get_analytics as db_get_analytics

    days = request.args.get('days', 30, type=int)
    days = min(days, 365)  # Max 1 year

    data = db_get_analytics(g.account_id, days)
    return jsonify(data)


@api.route('/analytics/history')
@require_account
def get_history():
    """Get follower history events."""
    from src.core.database import get_session, FollowerHistory

    days = request.args.get('days', 30, type=int)
    event_type = request.args.get('event_type')
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)

    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        query = session.query(FollowerHistory).filter(
            FollowerHistory.account_id == g.account_id,
            FollowerHistory.event_time >= cutoff
        )

        if event_type:
            query = query.filter(FollowerHistory.event_type == event_type)

        total = query.count()
        events = query.order_by(FollowerHistory.event_time.desc()) \
            .offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            'events': [
                {
                    'id': e.id,
                    'username': e.username,
                    'type': e.event_type,
                    'time': e.event_time.isoformat(),
                    'follower_count': e.follower_count_at_event,
                    'following_count': e.following_count_at_event
                }
                for e in events
            ],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })


@api.route('/rate-limit')
def get_rate_limit():
    """Get GitHub API rate limit status."""
    from src.core.github_api import get_rate_limit_status

    try:
        rate_limit = get_rate_limit_status()
        return jsonify({
            'limit': rate_limit['limit'],
            'remaining': rate_limit['remaining'],
            'reset_at': rate_limit['resetAt']
        })
    except Exception as e:
        logger.error(f"Error fetching rate limit: {e}")
        return jsonify({'error': str(e)}), 500


# ============== Export Routes ==============

@api.route('/export')
@require_account
def export_data():
    """Export data as JSON or CSV."""
    from src.core.database import get_session, FollowerHistory, FollowerSnapshot, get_analytics
    from src.core.github_api import get_followers_with_counts, get_following

    export_format = request.args.get('format', 'json')
    export_type = request.args.get('type', 'followers')
    days = request.args.get('days', 30, type=int)

    if export_format not in ['json', 'csv']:
        return jsonify({'error': 'Invalid format. Use json or csv'}), 400

    data = {}
    filename = f"github_tracker_{export_type}_{datetime.now().strftime('%Y%m%d')}"

    try:
        if export_type == 'followers':
            data = {'followers': get_followers_with_counts()}
        elif export_type == 'following':
            data = {'following': get_following()}
        elif export_type == 'history':
            with get_session() as session:
                cutoff = datetime.utcnow() - timedelta(days=days)
                events = session.query(FollowerHistory).filter(
                    FollowerHistory.account_id == g.account_id,
                    FollowerHistory.event_time >= cutoff
                ).order_by(FollowerHistory.event_time.desc()).all()

                data = {
                    'history': [
                        {
                            'username': e.username,
                            'event_type': e.event_type,
                            'event_time': e.event_time.isoformat(),
                            'follower_count': e.follower_count_at_event,
                            'following_count': e.following_count_at_event
                        }
                        for e in events
                    ]
                }
        elif export_type == 'analytics':
            data = get_analytics(g.account_id, days)
        elif export_type == 'all':
            data = {
                'followers': get_followers_with_counts(),
                'following': get_following(),
                'analytics': get_analytics(g.account_id, days)
            }
        else:
            return jsonify({'error': 'Invalid export type'}), 400

        if export_format == 'json':
            return Response(
                json.dumps(data, indent=2, default=str),
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename={filename}.json'}
            )
        else:  # CSV
            output = io.StringIO()
            if export_type in ['followers', 'following']:
                items = data.get(export_type, [])
                if items:
                    writer = csv.DictWriter(output, fieldnames=items[0].keys())
                    writer.writeheader()
                    writer.writerows(items)
            elif export_type == 'history':
                items = data.get('history', [])
                if items:
                    writer = csv.DictWriter(output, fieldnames=items[0].keys())
                    writer.writeheader()
                    writer.writerows(items)

            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename={filename}.csv'}
            )

    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500


# ============== Whitelist Routes ==============

@api.route('/whitelist', methods=['GET'])
@require_account
def get_whitelist():
    """Get whitelisted users."""
    from src.core.database import get_session, UserMetadata

    with get_session() as session:
        users = session.query(UserMetadata).filter_by(
            account_id=g.account_id,
            is_whitelisted=True
        ).all()

        return jsonify({
            'whitelist': [u.username for u in users]
        })


@api.route('/whitelist', methods=['POST'])
@require_account
def add_to_whitelist():
    """Add user to whitelist."""
    from src.core.database import get_session, UserMetadata

    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip().lower()

    if not username:
        return jsonify({'error': 'Username is required'}), 400

    with get_session() as session:
        metadata = session.query(UserMetadata).filter_by(
            account_id=g.account_id,
            username=username
        ).first()

        if not metadata:
            metadata = UserMetadata(
                account_id=g.account_id,
                username=username,
                is_whitelisted=True
            )
            session.add(metadata)
        else:
            metadata.is_whitelisted = True

        # Get updated list
        users = session.query(UserMetadata).filter_by(
            account_id=g.account_id,
            is_whitelisted=True
        ).all()

        return jsonify({'whitelist': [u.username for u in users]})


@api.route('/whitelist', methods=['DELETE'])
@require_account
def remove_from_whitelist():
    """Remove user from whitelist."""
    from src.core.database import get_session, UserMetadata

    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip().lower()

    if not username:
        return jsonify({'error': 'Username is required'}), 400

    with get_session() as session:
        metadata = session.query(UserMetadata).filter_by(
            account_id=g.account_id,
            username=username
        ).first()

        if metadata:
            metadata.is_whitelisted = False

        users = session.query(UserMetadata).filter_by(
            account_id=g.account_id,
            is_whitelisted=True
        ).all()

        return jsonify({'whitelist': [u.username for u in users]})


# ============== User Metadata Routes ==============

@api.route('/user/<username>/metadata', methods=['GET'])
@require_account
def get_user_metadata(username):
    """Get metadata for a user."""
    from src.core.database import get_session, UserMetadata

    username = username.strip().lower()

    with get_session() as session:
        metadata = session.query(UserMetadata).filter_by(
            account_id=g.account_id,
            username=username
        ).first()

        if not metadata:
            return jsonify({
                'username': username,
                'is_whitelisted': False,
                'is_ignored': False,
                'notes': None,
                'tags': [],
                'followed_at': None,
                'follow_back_deadline': None
            })

        return jsonify({
            'username': metadata.username,
            'is_whitelisted': metadata.is_whitelisted,
            'is_ignored': metadata.is_ignored,
            'notes': metadata.notes,
            'tags': metadata.get_tags_list(),
            'followed_at': metadata.followed_at.isoformat() if metadata.followed_at else None,
            'follow_back_deadline': metadata.follow_back_deadline.isoformat() if metadata.follow_back_deadline else None,
            'avatar_url': metadata.avatar_url,
            'bio': metadata.bio,
            'follower_count': metadata.follower_count,
            'following_count': metadata.following_count
        })


@api.route('/user/<username>/metadata', methods=['PUT'])
@require_account
def update_user_metadata(username):
    """Update metadata for a user."""
    from src.core.database import get_session, UserMetadata

    username = username.strip().lower()
    data = request.get_json(silent=True) or {}

    with get_session() as session:
        metadata = session.query(UserMetadata).filter_by(
            account_id=g.account_id,
            username=username
        ).first()

        if not metadata:
            metadata = UserMetadata(
                account_id=g.account_id,
                username=username
            )
            session.add(metadata)

        if 'notes' in data:
            metadata.notes = data['notes']
        if 'tags' in data:
            metadata.set_tags_list(data['tags'])
        if 'is_whitelisted' in data:
            metadata.is_whitelisted = data['is_whitelisted']
        if 'is_ignored' in data:
            metadata.is_ignored = data['is_ignored']

        return jsonify({
            'username': metadata.username,
            'notes': metadata.notes,
            'tags': metadata.get_tags_list(),
            'is_whitelisted': metadata.is_whitelisted,
            'is_ignored': metadata.is_ignored
        })


# ============== Tags Routes ==============

@api.route('/tags')
@require_account
def get_all_tags():
    """Get all tags with user counts."""
    from src.core.database import get_session, UserMetadata
    from collections import Counter

    with get_session() as session:
        users = session.query(UserMetadata).filter(
            UserMetadata.account_id == g.account_id,
            UserMetadata.tags.isnot(None),
            UserMetadata.tags != ''
        ).all()

        tag_counts = Counter()
        for user in users:
            for tag in user.get_tags_list():
                tag_counts[tag] += 1

        return jsonify({
            'tags': [
                {'name': tag, 'count': count}
                for tag, count in sorted(tag_counts.items())
            ]
        })


@api.route('/tags/<tag>/users')
@require_account
def get_users_by_tag(tag):
    """Get users with a specific tag."""
    from src.core.database import get_session, UserMetadata

    tag = tag.strip().lower()

    with get_session() as session:
        users = session.query(UserMetadata).filter(
            UserMetadata.account_id == g.account_id,
            UserMetadata.tags.contains(tag)
        ).all()

        # Filter to exact tag matches
        matching_users = [
            u for u in users
            if tag in u.get_tags_list()
        ]

        return jsonify({
            'tag': tag,
            'users': [
                {
                    'username': u.username,
                    'notes': u.notes,
                    'tags': u.get_tags_list()
                }
                for u in matching_users
            ]
        })


# ============== Follow-back Deadline Routes ==============

@api.route('/follow-back-deadlines')
@require_account
def get_deadlines():
    """Get users with follow-back deadlines."""
    from src.core.database import get_session, UserMetadata

    with get_session() as session:
        users = session.query(UserMetadata).filter(
            UserMetadata.account_id == g.account_id,
            UserMetadata.follow_back_deadline.isnot(None)
        ).order_by(UserMetadata.follow_back_deadline).all()

        now = datetime.utcnow()
        return jsonify({
            'deadlines': [
                {
                    'username': u.username,
                    'followed_at': u.followed_at.isoformat() if u.followed_at else None,
                    'deadline': u.follow_back_deadline.isoformat(),
                    'days_remaining': (u.follow_back_deadline - now).days,
                    'is_overdue': u.follow_back_deadline < now
                }
                for u in users
            ]
        })


@api.route('/follow-back-deadlines/<username>', methods=['PUT'])
@require_account
def set_deadline(username):
    """Set follow-back deadline for a user."""
    from src.core.database import get_session, UserMetadata

    username = username.strip().lower()
    data = request.get_json(silent=True) or {}
    deadline_days = data.get('deadline_days', 7)

    if not 1 <= deadline_days <= 365:
        return jsonify({'error': 'Deadline must be between 1 and 365 days'}), 400

    with get_session() as session:
        metadata = session.query(UserMetadata).filter_by(
            account_id=g.account_id,
            username=username
        ).first()

        if not metadata:
            metadata = UserMetadata(
                account_id=g.account_id,
                username=username
            )
            session.add(metadata)

        now = datetime.utcnow()
        if not metadata.followed_at:
            metadata.followed_at = now
        metadata.follow_back_deadline = now + timedelta(days=deadline_days)

        return jsonify({
            'username': username,
            'followed_at': metadata.followed_at.isoformat(),
            'deadline': metadata.follow_back_deadline.isoformat()
        })


@api.route('/follow-back-deadlines/<username>', methods=['DELETE'])
@require_account
def remove_deadline(username):
    """Remove follow-back deadline for a user."""
    from src.core.database import get_session, UserMetadata

    username = username.strip().lower()

    with get_session() as session:
        metadata = session.query(UserMetadata).filter_by(
            account_id=g.account_id,
            username=username
        ).first()

        if metadata:
            metadata.follow_back_deadline = None

        return jsonify({'success': True})


# ============== Account Routes ==============

@api.route('/accounts', methods=['GET'])
def list_accounts():
    """List all accounts."""
    from src.core.database import get_session, Account

    with get_session() as session:
        accounts = session.query(Account).all()
        return jsonify({
            'accounts': [
                {
                    'id': a.id,
                    'username': a.username,
                    'is_active': a.is_active,
                    'is_default': a.is_default,
                    'created_at': a.created_at.isoformat()
                }
                for a in accounts
            ]
        })


@api.route('/accounts', methods=['POST'])
def create_account():
    """Create a new account."""
    from src.core.database import get_or_create_account

    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    token = data.get('token', '').strip()
    is_default = data.get('is_default', False)

    if not username or not token:
        return jsonify({'error': 'Username and token are required'}), 400

    try:
        account = get_or_create_account(username, token, is_default)
        return jsonify({
            'id': account.id,
            'username': account.username,
            'is_default': account.is_default
        }), 201
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        return jsonify({'error': str(e)}), 500


@api.route('/accounts/<int:account_id>', methods=['GET'])
def get_account(account_id):
    """Get account details."""
    from src.core.database import get_session, Account

    with get_session() as session:
        account = session.query(Account).filter_by(id=account_id).first()
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        return jsonify({
            'id': account.id,
            'username': account.username,
            'is_active': account.is_active,
            'is_default': account.is_default,
            'created_at': account.created_at.isoformat()
        })


@api.route('/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    """Update account settings."""
    from src.core.database import get_session, Account

    data = request.get_json(silent=True) or {}

    with get_session() as session:
        account = session.query(Account).filter_by(id=account_id).first()
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        if 'token' in data:
            account.token = data['token']
        if 'is_active' in data:
            account.is_active = data['is_active']
        if data.get('is_default'):
            session.query(Account).filter(Account.id != account_id).update({'is_default': False})
            account.is_default = True

        return jsonify({
            'id': account.id,
            'username': account.username,
            'is_active': account.is_active,
            'is_default': account.is_default
        })


@api.route('/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Delete an account."""
    from src.core.database import get_session, Account

    with get_session() as session:
        account = session.query(Account).filter_by(id=account_id).first()
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        session.delete(account)
        return jsonify({'success': True})


@api.route('/accounts/<int:account_id>/switch', methods=['POST'])
def switch_account(account_id):
    """Switch to a different account."""
    from src.core.database import get_session, Account

    with get_session() as session:
        account = session.query(Account).filter_by(id=account_id).first()
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        session.query(Account).update({'is_default': False})
        account.is_default = True

        return jsonify({
            'id': account.id,
            'username': account.username,
            'is_default': True
        })


# ============== Webhook Routes ==============

@api.route('/webhooks', methods=['GET'])
@require_account
def list_webhooks():
    """List webhooks."""
    from src.core.database import get_session, Webhook

    with get_session() as session:
        webhooks = session.query(Webhook).filter_by(account_id=g.account_id).all()
        return jsonify({
            'webhooks': [
                {
                    'id': w.id,
                    'name': w.name,
                    'url': w.url,
                    'is_active': w.is_active,
                    'events': w.get_events_list(),
                    'last_triggered': w.last_triggered.isoformat() if w.last_triggered else None,
                    'success_count': w.success_count,
                    'failure_count': w.failure_count
                }
                for w in webhooks
            ]
        })


@api.route('/webhooks', methods=['POST'])
@require_account
def create_webhook():
    """Create a webhook."""
    from src.core.database import get_session, Webhook

    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    secret = data.get('secret')
    events = data.get('events', ['all'])

    if not name or not url:
        return jsonify({'error': 'Name and URL are required'}), 400

    with get_session() as session:
        webhook = Webhook(
            account_id=g.account_id,
            name=name,
            url=url,
            secret=secret,
            events=','.join(events) if isinstance(events, list) else events
        )
        session.add(webhook)
        session.flush()

        return jsonify({
            'id': webhook.id,
            'name': webhook.name,
            'url': webhook.url,
            'events': webhook.get_events_list()
        }), 201


@api.route('/webhooks/<int:webhook_id>', methods=['PUT'])
@require_account
def update_webhook(webhook_id):
    """Update a webhook."""
    from src.core.database import get_session, Webhook

    data = request.get_json(silent=True) or {}

    with get_session() as session:
        webhook = session.query(Webhook).filter_by(
            id=webhook_id,
            account_id=g.account_id
        ).first()

        if not webhook:
            return jsonify({'error': 'Webhook not found'}), 404

        if 'name' in data:
            webhook.name = data['name']
        if 'url' in data:
            webhook.url = data['url']
        if 'secret' in data:
            webhook.secret = data['secret']
        if 'events' in data:
            events = data['events']
            webhook.events = ','.join(events) if isinstance(events, list) else events
        if 'is_active' in data:
            webhook.is_active = data['is_active']

        return jsonify({
            'id': webhook.id,
            'name': webhook.name,
            'url': webhook.url,
            'is_active': webhook.is_active,
            'events': webhook.get_events_list()
        })


@api.route('/webhooks/<int:webhook_id>', methods=['DELETE'])
@require_account
def delete_webhook(webhook_id):
    """Delete a webhook."""
    from src.core.database import get_session, Webhook

    with get_session() as session:
        webhook = session.query(Webhook).filter_by(
            id=webhook_id,
            account_id=g.account_id
        ).first()

        if not webhook:
            return jsonify({'error': 'Webhook not found'}), 404

        session.delete(webhook)
        return jsonify({'success': True})


@api.route('/webhooks/<int:webhook_id>/test', methods=['POST'])
@require_account
def test_webhook(webhook_id):
    """Test a webhook."""
    from src.core.database import get_session, Webhook
    from src.services.notifications import WebhookManager

    with get_session() as session:
        webhook = session.query(Webhook).filter_by(
            id=webhook_id,
            account_id=g.account_id
        ).first()

        if not webhook:
            return jsonify({'error': 'Webhook not found'}), 404

        manager = WebhookManager()
        success = manager.send_webhook(
            webhook.url,
            {
                'event': 'test',
                'timestamp': datetime.utcnow().isoformat(),
                'data': {'message': 'This is a test webhook'}
            },
            webhook.secret
        )

        if success:
            webhook.success_count += 1
        else:
            webhook.failure_count += 1
        webhook.last_triggered = datetime.utcnow()

        return jsonify({'success': success})


# ============== Schedule Routes ==============

@api.route('/schedule', methods=['GET'])
@require_account
def get_schedule():
    """Get schedule configuration."""
    from src.core.database import get_session, ScheduleConfig

    with get_session() as session:
        configs = session.query(ScheduleConfig).filter_by(account_id=g.account_id).all()
        return jsonify({
            'schedules': [
                {
                    'id': c.id,
                    'task_name': c.task_name,
                    'is_enabled': c.is_enabled,
                    'hour': c.hour,
                    'minute': c.minute,
                    'day_of_month': c.day_of_month,
                    'day_of_week': c.day_of_week,
                    'dry_run': c.dry_run,
                    'last_run': c.last_run.isoformat() if c.last_run else None,
                    'next_run': c.next_run.isoformat() if c.next_run else None
                }
                for c in configs
            ]
        })


@api.route('/schedule', methods=['PUT'])
@require_account
def update_schedule():
    """Update schedule configuration."""
    from src.core.database import get_session, ScheduleConfig

    data = request.get_json(silent=True) or {}
    task_name = data.get('task_name')

    if not task_name:
        return jsonify({'error': 'task_name is required'}), 400

    with get_session() as session:
        config = session.query(ScheduleConfig).filter_by(
            account_id=g.account_id,
            task_name=task_name
        ).first()

        if not config:
            config = ScheduleConfig(
                account_id=g.account_id,
                task_name=task_name
            )
            session.add(config)

        if 'is_enabled' in data:
            config.is_enabled = data['is_enabled']
        if 'hour' in data:
            config.hour = data['hour']
        if 'minute' in data:
            config.minute = data['minute']
        if 'day_of_month' in data:
            config.day_of_month = data['day_of_month']
        if 'day_of_week' in data:
            config.day_of_week = data['day_of_week']
        if 'dry_run' in data:
            config.dry_run = data['dry_run']
        if 'parameters' in data:
            config.parameters = json.dumps(data['parameters'])

        return jsonify({
            'task_name': config.task_name,
            'is_enabled': config.is_enabled,
            'hour': config.hour,
            'minute': config.minute,
            'dry_run': config.dry_run
        })


@api.route('/schedule/run', methods=['POST'])
@require_account
def run_scheduled_task():
    """Manually run a scheduled task."""
    from daily_tasks import run_daily_tasks
    from monthly_tasks import run_monthly_tasks

    data = request.get_json(silent=True) or {}
    task = data.get('task')
    dry_run = data.get('dry_run', False)

    if task not in ['daily_follow', 'monthly_unfollow']:
        return jsonify({'error': 'Invalid task'}), 400

    try:
        if dry_run:
            # Return preview without executing
            if task == 'daily_follow':
                from src.core.github_api import get_random_users
                users = get_random_users()
                return jsonify({
                    'task': task,
                    'dry_run': True,
                    'would_follow': [u['login'] for u in users]
                })
            else:
                from src.core.github_api import get_followers, get_following
                from src.services.data_manager import load_ignore_list
                followers = set(f.lower() for f in get_followers())
                following = get_following()
                ignore_list = set(load_ignore_list())
                not_following_back = [
                    f['login'] for f in following
                    if f['login'].lower() not in followers and f['login'].lower() not in ignore_list
                ]
                return jsonify({
                    'task': task,
                    'dry_run': True,
                    'would_unfollow': not_following_back
                })
        else:
            if task == 'daily_follow':
                run_daily_tasks()
            else:
                run_monthly_tasks()

            return jsonify({'task': task, 'success': True})

    except Exception as e:
        logger.error(f"Error running task {task}: {e}")
        return jsonify({'error': str(e)}), 500


# ============== Action History & Undo Routes ==============

@api.route('/actions/history')
@require_account
def get_action_history():
    """Get action history."""
    from src.core.database import get_recent_actions

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)

    actions = get_recent_actions(g.account_id, limit=per_page * page)
    start = (page - 1) * per_page
    end = start + per_page

    return jsonify({
        'actions': actions[start:end],
        'pagination': {
            'page': page,
            'per_page': per_page
        }
    })


@api.route('/actions/<int:action_id>/undo', methods=['POST'])
@require_account
def undo_action(action_id):
    """Undo an action."""
    from src.core.database import get_session, ActionLog
    from src.core.github_api import follow_user, unfollow_user, bulk_follow_users, bulk_unfollow_users

    with get_session() as session:
        action = session.query(ActionLog).filter_by(
            id=action_id,
            account_id=g.account_id
        ).first()

        if not action:
            return jsonify({'error': 'Action not found'}), 404

        if action.is_undone:
            return jsonify({'error': 'Action already undone'}), 400

        try:
            if action.action_type == 'follow':
                success, msg = unfollow_user(action.target_username)
            elif action.action_type == 'unfollow':
                success, msg = follow_user(action.target_username)
            elif action.action_type == 'bulk_follow':
                usernames = json.loads(action.target_usernames or '[]')
                results = bulk_unfollow_users(usernames)
                success = all(r.get('success') for r in results.values())
                msg = ''
            elif action.action_type == 'bulk_unfollow':
                usernames = json.loads(action.target_usernames or '[]')
                results = bulk_follow_users(usernames)
                success = all(r.get('success') for r in results.values())
                msg = ''
            else:
                return jsonify({'error': 'Cannot undo this action type'}), 400

            if success:
                action.is_undone = True
                action.undone_at = datetime.utcnow()

            return jsonify({
                'success': success,
                'message': msg
            })

        except Exception as e:
            logger.error(f"Error undoing action {action_id}: {e}")
            return jsonify({'error': str(e)}), 500


# ============== Notification Config Routes ==============

@api.route('/notifications/config', methods=['GET'])
@require_account
def get_notification_config():
    """Get notification configuration."""
    from src.core.database import get_session, NotificationConfig

    with get_session() as session:
        config = session.query(NotificationConfig).filter_by(account_id=g.account_id).first()

        if not config:
            return jsonify({
                'email_enabled': False,
                'notify_on_follow': True,
                'notify_on_unfollow': True,
                'notify_on_milestone': True,
                'daily_digest_enabled': False,
                'weekly_digest_enabled': False,
                'milestone_thresholds': [100, 500, 1000, 5000, 10000]
            })

        return jsonify({
            'email_enabled': config.email_enabled,
            'email_address': config.email_address,
            'smtp_host': config.smtp_host,
            'smtp_port': config.smtp_port,
            'smtp_username': config.smtp_username,
            'notify_on_follow': config.notify_on_follow,
            'notify_on_unfollow': config.notify_on_unfollow,
            'notify_on_milestone': config.notify_on_milestone,
            'daily_digest_enabled': config.daily_digest_enabled,
            'daily_digest_hour': config.daily_digest_hour,
            'weekly_digest_enabled': config.weekly_digest_enabled,
            'weekly_digest_day': config.weekly_digest_day,
            'milestone_thresholds': json.loads(config.milestone_thresholds or '[]')
        })


@api.route('/notifications/config', methods=['PUT'])
@require_account
def update_notification_config():
    """Update notification configuration."""
    from src.core.database import get_session, NotificationConfig

    data = request.get_json(silent=True) or {}

    with get_session() as session:
        config = session.query(NotificationConfig).filter_by(account_id=g.account_id).first()

        if not config:
            config = NotificationConfig(account_id=g.account_id)
            session.add(config)

        for field in ['email_enabled', 'email_address', 'smtp_host', 'smtp_port',
                      'smtp_username', 'smtp_password', 'smtp_use_tls',
                      'notify_on_follow', 'notify_on_unfollow', 'notify_on_milestone',
                      'daily_digest_enabled', 'daily_digest_hour',
                      'weekly_digest_enabled', 'weekly_digest_day']:
            if field in data:
                setattr(config, field, data[field])

        if 'milestone_thresholds' in data:
            config.milestone_thresholds = json.dumps(data['milestone_thresholds'])

        return jsonify({'success': True})
