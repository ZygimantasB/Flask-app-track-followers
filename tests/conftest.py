"""
Pytest configuration and fixtures for GitHub Followers Tracker tests.
"""
import os
import sys
import pytest
import tempfile
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables before importing app modules
os.environ['GITHUB_TOKEN'] = 'test_token_12345'
os.environ['GITHUB_USERNAME'] = 'test_user'
os.environ['GFT_DATABASE_PATH'] = ':memory:'


@pytest.fixture(scope='session')
def app():
    """Create Flask application for testing."""
    # Import after setting env vars
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    return flask_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def db_session():
    """Create a fresh database session for testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, scoped_session
    from src.core.database import Base

    # Create in-memory SQLite database
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)

    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()

    yield session

    session.close()
    Session.remove()


@pytest.fixture
def mock_github_api():
    """Mock GitHub API responses."""
    with patch('src.core.github_api.session') as mock_session:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'viewer': {
                    'followers': {
                        'nodes': [
                            {'login': 'follower1'},
                            {'login': 'follower2'},
                        ],
                        'pageInfo': {
                            'hasNextPage': False,
                            'endCursor': None
                        }
                    }
                }
            }
        }
        mock_session.post.return_value = mock_response
        mock_session.get.return_value = mock_response
        yield mock_session


@pytest.fixture
def sample_followers():
    """Sample follower data for testing."""
    return [
        {
            'login': 'user1',
            'followers': 100,
            'following': 50,
            'bio': 'Developer',
            'public_repos': 10,
            'type': 'User'
        },
        {
            'login': 'user2',
            'followers': 200,
            'following': 150,
            'bio': 'Designer',
            'public_repos': 5,
            'type': 'User'
        },
        {
            'login': 'user3',
            'followers': 50,
            'following': 25,
            'bio': None,
            'public_repos': 20,
            'type': 'User'
        }
    ]


@pytest.fixture
def sample_following():
    """Sample following data for testing."""
    return [
        {
            'login': 'following1',
            'type': 'User',
            'id': 'MDQ6VXNlcjEyMzQ1',
            'followers': 500,
            'following': 100
        },
        {
            'login': 'following2',
            'type': 'Organization',
            'id': 'MDEyOk9yZ2FuaXphdGlvbjY3ODkw',
            'followers': 1000,
            'following': 0
        }
    ]


@pytest.fixture
def mock_rate_limit():
    """Mock rate limit response."""
    return {
        'limit': 5000,
        'cost': 1,
        'remaining': 4999,
        'resetAt': '2024-01-01T00:00:00Z'
    }


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory."""
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def temp_ignore_list(temp_data_dir):
    """Create temporary ignore list file."""
    ignore_file = temp_data_dir / 'ignore_list.txt'
    ignore_file.write_text('ignored_user1\nignored_user2\n')
    return ignore_file


@pytest.fixture
def mock_graphql_response():
    """Factory for creating mock GraphQL responses."""
    def _create_response(data, errors=None):
        response = {'data': data}
        if errors:
            response['errors'] = errors
        return response
    return _create_response


@pytest.fixture
def test_account(db_session):
    """Create a test account in the database."""
    from src.core.database import Account

    account = Account(
        username='test_user',
        token='test_token',
        is_active=True,
        is_default=True
    )
    db_session.add(account)
    db_session.commit()
    return account


class MockResponse:
    """Helper class to mock requests responses."""

    def __init__(self, json_data, status_code=200, headers=None):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = headers or {}
        self.text = json.dumps(json_data)

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error: {self.status_code}")


@pytest.fixture
def mock_response():
    """Factory for creating mock responses."""
    return MockResponse
