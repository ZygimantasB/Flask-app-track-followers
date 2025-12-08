"""
Notification system for GitHub Followers Tracker.
Supports webhooks, email notifications, and milestone alerts.
"""
import json
import hmac
import hashlib
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Event types
EVENT_FOLLOWER_GAINED = 'follower_gained'
EVENT_FOLLOWER_LOST = 'follower_lost'
EVENT_YOU_FOLLOWED = 'you_followed'
EVENT_YOU_UNFOLLOWED = 'you_unfollowed'
EVENT_MILESTONE_REACHED = 'milestone_reached'
EVENT_DAILY_DIGEST = 'daily_digest'
EVENT_WEEKLY_DIGEST = 'weekly_digest'

ALL_EVENTS = [
    EVENT_FOLLOWER_GAINED,
    EVENT_FOLLOWER_LOST,
    EVENT_YOU_FOLLOWED,
    EVENT_YOU_UNFOLLOWED,
    EVENT_MILESTONE_REACHED,
    EVENT_DAILY_DIGEST,
    EVENT_WEEKLY_DIGEST
]


class WebhookManager:
    """Manages webhook notifications."""

    def __init__(self, max_workers: int = 3):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def send_webhook(self, url: str, payload: Dict, secret: str = None,
                     timeout: int = 10) -> bool:
        """Send a webhook notification."""
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'GitHub-Followers-Tracker/1.0'
            }

            body = json.dumps(payload, default=str)

            if secret:
                signature = hmac.new(
                    secret.encode('utf-8'),
                    body.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers['X-Hub-Signature-256'] = f'sha256={signature}'

            response = requests.post(
                url,
                data=body,
                headers=headers,
                timeout=timeout
            )

            if response.status_code < 300:
                logger.info(f"Webhook sent successfully to {url}")
                return True
            else:
                logger.warning(f"Webhook failed: {url} returned {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook error for {url}: {e}")
            return False

    def send_webhook_async(self, url: str, payload: Dict, secret: str = None):
        """Send webhook asynchronously."""
        self.executor.submit(self.send_webhook, url, payload, secret)

    def trigger_event(self, webhooks: List[Dict], event_type: str, data: Dict):
        """Trigger webhooks for an event."""
        payload = {
            'event': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }

        for webhook in webhooks:
            events = webhook.get('events', ['all'])
            if 'all' in events or event_type in events:
                if webhook.get('is_active', True):
                    self.send_webhook_async(
                        webhook['url'],
                        payload,
                        webhook.get('secret')
                    )


class EmailNotifier:
    """Handles email notifications."""

    def __init__(self, config: Dict):
        self.enabled = config.get('email_enabled', False)
        self.email_address = config.get('email_address')
        self.smtp_host = config.get('smtp_host')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.use_tls = config.get('smtp_use_tls', True)

    def send_email(self, subject: str, body: str, html_body: str = None) -> bool:
        """Send an email notification."""
        if not self.enabled or not self.email_address:
            logger.debug("Email notifications disabled or no address configured")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_username or self.email_address
            msg['To'] = self.email_address

            msg.attach(MIMEText(body, 'plain'))

            if html_body:
                msg.attach(MIMEText(html_body, 'html'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False


class NotificationService:
    """Main notification service coordinating webhooks and emails."""

    def __init__(self):
        self.webhook_manager = WebhookManager()
        self._email_notifiers = {}

    def get_email_notifier(self, account_id: int) -> Optional[EmailNotifier]:
        """Get or create email notifier for an account."""
        from src.core.database import get_session, NotificationConfig

        if account_id not in self._email_notifiers:
            with get_session() as session:
                config = session.query(NotificationConfig).filter_by(
                    account_id=account_id
                ).first()

                if config:
                    self._email_notifiers[account_id] = EmailNotifier({
                        'email_enabled': config.email_enabled,
                        'email_address': config.email_address,
                        'smtp_host': config.smtp_host,
                        'smtp_port': config.smtp_port,
                        'smtp_username': config.smtp_username,
                        'smtp_password': config.smtp_password,
                        'smtp_use_tls': config.smtp_use_tls
                    })
                else:
                    return None

        return self._email_notifiers.get(account_id)

    def get_webhooks(self, account_id: int) -> List[Dict]:
        """Get active webhooks for an account."""
        from src.core.database import get_session, Webhook

        with get_session() as session:
            webhooks = session.query(Webhook).filter_by(
                account_id=account_id,
                is_active=True
            ).all()

            return [
                {
                    'id': w.id,
                    'url': w.url,
                    'secret': w.secret,
                    'events': w.get_events_list(),
                    'is_active': w.is_active
                }
                for w in webhooks
            ]

    def notify_follower_gained(self, account_id: int, username: str, follower_count: int):
        """Notify about a new follower."""
        webhooks = self.get_webhooks(account_id)
        self.webhook_manager.trigger_event(
            webhooks,
            EVENT_FOLLOWER_GAINED,
            {
                'username': username,
                'current_follower_count': follower_count
            }
        )

        notifier = self.get_email_notifier(account_id)
        if notifier:
            notifier.send_email(
                f"New GitHub Follower: {username}",
                f"You have a new follower: {username}\n\nYour current follower count: {follower_count}",
                f"""
                <h2>New GitHub Follower</h2>
                <p>You have a new follower: <strong><a href="https://github.com/{username}">{username}</a></strong></p>
                <p>Your current follower count: <strong>{follower_count}</strong></p>
                """
            )

    def notify_follower_lost(self, account_id: int, username: str, follower_count: int):
        """Notify about an unfollower."""
        webhooks = self.get_webhooks(account_id)
        self.webhook_manager.trigger_event(
            webhooks,
            EVENT_FOLLOWER_LOST,
            {
                'username': username,
                'current_follower_count': follower_count
            }
        )

        notifier = self.get_email_notifier(account_id)
        if notifier:
            notifier.send_email(
                f"GitHub Unfollower: {username}",
                f"{username} unfollowed you.\n\nYour current follower count: {follower_count}",
                f"""
                <h2>GitHub Unfollower</h2>
                <p><strong><a href="https://github.com/{username}">{username}</a></strong> unfollowed you.</p>
                <p>Your current follower count: <strong>{follower_count}</strong></p>
                """
            )

    def notify_milestone(self, account_id: int, milestone_type: str, threshold: int, current_count: int):
        """Notify about reaching a milestone."""
        webhooks = self.get_webhooks(account_id)
        self.webhook_manager.trigger_event(
            webhooks,
            EVENT_MILESTONE_REACHED,
            {
                'milestone_type': milestone_type,
                'threshold': threshold,
                'current_count': current_count
            }
        )

        notifier = self.get_email_notifier(account_id)
        if notifier:
            notifier.send_email(
                f"Milestone Reached: {threshold} {milestone_type}!",
                f"Congratulations! You've reached {threshold} {milestone_type}!\n\nCurrent count: {current_count}",
                f"""
                <h2>Milestone Reached!</h2>
                <p>Congratulations! You've reached <strong>{threshold} {milestone_type}</strong>!</p>
                <p>Current count: <strong>{current_count}</strong></p>
                """
            )

    def check_milestones(self, account_id: int, follower_count: int, following_count: int):
        """Check and trigger milestone notifications."""
        from src.core.database import get_session, NotificationConfig, Milestone

        with get_session() as session:
            config = session.query(NotificationConfig).filter_by(
                account_id=account_id
            ).first()

            if not config or not config.notify_on_milestone:
                return

            thresholds = json.loads(config.milestone_thresholds or '[100, 500, 1000, 5000, 10000]')

            for threshold in thresholds:
                if follower_count >= threshold:
                    existing = session.query(Milestone).filter_by(
                        account_id=account_id,
                        milestone_type='followers',
                        threshold=threshold
                    ).first()

                    if not existing:
                        milestone = Milestone(
                            account_id=account_id,
                            milestone_type='followers',
                            threshold=threshold,
                            notified=True
                        )
                        session.add(milestone)
                        self.notify_milestone(account_id, 'followers', threshold, follower_count)

    def send_daily_digest(self, account_id: int):
        """Send daily digest email."""
        from src.core.database import get_analytics

        analytics = get_analytics(account_id, days=1)

        if not analytics['events']:
            return

        webhooks = self.get_webhooks(account_id)
        self.webhook_manager.trigger_event(
            webhooks,
            EVENT_DAILY_DIGEST,
            analytics
        )

        notifier = self.get_email_notifier(account_id)
        if notifier:
            events = analytics['events']

            gained = [e for e in events if e['type'] == 'followed']
            lost = [e for e in events if e['type'] == 'unfollowed']

            body = f"""Daily GitHub Followers Digest

Summary:
- New followers: {len(gained)}
- Unfollowers: {len(lost)}
- Net change: {len(gained) - len(lost)}

"""
            if gained:
                body += "New followers:\n" + "\n".join(f"  - {e['username']}" for e in gained) + "\n\n"
            if lost:
                body += "Unfollowers:\n" + "\n".join(f"  - {e['username']}" for e in lost)

            notifier.send_email(
                f"Daily GitHub Followers Digest",
                body
            )

    def send_weekly_digest(self, account_id: int):
        """Send weekly digest email."""
        from src.core.database import get_analytics

        analytics = get_analytics(account_id, days=7)

        webhooks = self.get_webhooks(account_id)
        self.webhook_manager.trigger_event(
            webhooks,
            EVENT_WEEKLY_DIGEST,
            analytics
        )

        notifier = self.get_email_notifier(account_id)
        if notifier:
            summary = analytics['summary']

            notifier.send_email(
                f"Weekly GitHub Followers Digest",
                f"""Weekly GitHub Followers Digest

Summary for the past 7 days:
- Total followers gained: {summary['total_gained']}
- Total followers lost: {summary['total_lost']}
- Net growth: {summary['total_growth']}
- Growth rate: {summary['growth_rate_percent']}%
"""
            )


# Global notification service instance
notification_service = NotificationService()
