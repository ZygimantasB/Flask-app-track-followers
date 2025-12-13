# Architecture Documentation

This document provides a detailed overview of the GitHub Followers Tracker architecture.

## System Overview

```mermaid
graph TB
    subgraph "Frontend"
        UI[Web UI - Single Page App]
        JS[JavaScript Modules]
        CSS[Styles - Dark/Light Theme]
    end

    subgraph "Backend"
        Flask[Flask Application]
        API[API Routes]
        Scheduler[APScheduler]
    end

    subgraph "Services"
        GitHubAPI[GitHub API Service]
        DB[Database Service]
        Cache[Cache Service]
        Notify[Notification Service]
        Auth[Auth Service]
        Encrypt[Encryption Service]
    end

    subgraph "Storage"
        SQLite[(SQLite Database)]
        Files[File Storage]
    end

    subgraph "External"
        GitHub[GitHub GraphQL API]
        SMTP[SMTP Server]
        Webhooks[Webhook Endpoints]
    end

    UI --> Flask
    JS --> API
    Flask --> API
    API --> GitHubAPI
    API --> DB
    API --> Cache
    API --> Notify
    API --> Auth
    Scheduler --> GitHubAPI
    GitHubAPI --> GitHub
    DB --> SQLite
    Cache --> Files
    Notify --> SMTP
    Notify --> Webhooks
    Encrypt --> DB
```

## Component Architecture

### Request Flow

```mermaid
sequenceDiagram
    participant User
    participant Flask
    participant Auth
    participant Cache
    participant DB
    participant GitHubAPI
    participant GitHub

    User->>Flask: GET /get_data?type=followers
    Flask->>Auth: Check authentication
    Auth-->>Flask: Authenticated

    Flask->>Cache: Is cache stale?
    alt Cache is stale
        Cache-->>Flask: Yes, need sync
        Flask->>GitHubAPI: Fetch followers
        GitHubAPI->>GitHub: GraphQL Query
        GitHub-->>GitHubAPI: Follower data
        GitHubAPI-->>Flask: Processed data
        Flask->>DB: Sync followers
        DB-->>Flask: Sync complete
    else Cache is fresh
        Cache-->>Flask: No, use cache
    end

    Flask->>DB: Get cached followers
    DB-->>Flask: Follower list
    Flask-->>User: JSON response
```

### Database Schema

```mermaid
erDiagram
    Account ||--o{ FollowerHistory : has
    Account ||--o{ FollowerSnapshot : has
    Account ||--o{ UserMetadata : has
    Account ||--o{ Webhook : has
    Account ||--o{ ScheduleConfig : has
    Account ||--o{ CachedFollower : has
    Account ||--o{ CachedFollowing : has
    Account ||--o{ SyncStatus : has
    Account ||--o{ ActionLog : has
    Account ||--o{ NotificationConfig : has
    Account ||--o{ Milestone : has

    Account {
        int id PK
        string username UK
        string token
        bool is_active
        bool is_default
        datetime created_at
    }

    CachedFollower {
        int id PK
        int account_id FK
        string username
        string bio
        int follower_count
        int following_count
        bool is_current
        datetime first_seen_at
        datetime last_seen_at
    }

    CachedFollowing {
        int id PK
        int account_id FK
        string username
        string user_type
        bool is_current
        datetime followed_at
    }

    FollowerHistory {
        int id PK
        int account_id FK
        string username
        string event_type
        datetime event_time
    }

    FollowerSnapshot {
        int id PK
        int account_id FK
        datetime snapshot_date
        int follower_count
        int following_count
        int new_followers
        int lost_followers
    }

    SyncStatus {
        int id PK
        int account_id FK
        string sync_type
        datetime last_sync_at
        bool last_sync_success
        int items_synced
    }

    UserMetadata {
        int id PK
        int account_id FK
        string username
        bool is_whitelisted
        bool is_ignored
        string notes
        string tags
    }

    Webhook {
        int id PK
        int account_id FK
        string name
        string url
        string secret
        string events
        bool is_active
    }
```

### Module Dependencies

```mermaid
graph LR
    subgraph "Entry Points"
        app[app.py]
        scheduler[scheduler.py]
    end

    subgraph "Core"
        github_api[github_api.py]
        database[database.py]
    end

    subgraph "Services"
        cache[cache.py]
        data_manager[data_manager.py]
        notifications[notifications.py]
        encryption[encryption.py]
        auth[auth.py]
    end

    subgraph "Tasks"
        daily[daily.py]
        monthly[monthly.py]
    end

    subgraph "API"
        routes[routes.py]
        docs[docs.py]
    end

    app --> github_api
    app --> database
    app --> routes
    app --> docs
    app --> daily
    app --> monthly
    app --> auth

    scheduler --> daily
    scheduler --> monthly
    scheduler --> github_api

    github_api --> cache
    database --> encryption
    notifications --> database

    routes --> github_api
    routes --> database
    routes --> data_manager

    daily --> github_api
    monthly --> github_api
```

## Data Flow

### Sync Process

```mermaid
flowchart TD
    A[Trigger Sync] --> B{Cache Stale?}
    B -->|Yes| C[Fetch from GitHub API]
    B -->|No| H[Return Cached Data]

    C --> D[Process GraphQL Response]
    D --> E[Compare with Existing Cache]
    E --> F{Changes Detected?}

    F -->|Yes| G[Update Database]
    F -->|No| H

    G --> I[Record Events]
    I --> J[Update Sync Status]
    J --> K[Trigger Notifications]
    K --> H

    H --> L[Apply Ignore List Filter]
    L --> M[Return to Client]
```

### Authentication Flow

```mermaid
flowchart TD
    A[Request] --> B{Auth Enabled?}
    B -->|No| C[Allow Access]
    B -->|Yes| D{Session Valid?}

    D -->|Yes| C
    D -->|No| E{API Token?}

    E -->|Valid| C
    E -->|Invalid/None| F{Basic Auth?}

    F -->|Valid| G[Create Session]
    F -->|Invalid/None| H[Redirect to Login]

    G --> C
    H --> I[Login Page]
    I --> J{Credentials Valid?}
    J -->|Yes| G
    J -->|No| K[Show Error]
    K --> I
```

## Directory Structure

```
github-followers-tracker/
├── app.py                    # Main Flask application
├── scheduler.py              # Standalone scheduler
├── alembic.ini              # Database migration config
├── pyproject.toml           # Project configuration
├── pytest.ini               # Test configuration
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
├── .pre-commit-config.yaml  # Pre-commit hooks
│
├── src/
│   ├── core/
│   │   ├── github_api.py    # GitHub API interactions
│   │   └── database.py      # SQLAlchemy models & operations
│   │
│   ├── services/
│   │   ├── auth.py          # Authentication service
│   │   ├── cache.py         # Caching utilities
│   │   ├── data_manager.py  # File-based data persistence
│   │   ├── encryption.py    # Encryption for sensitive data
│   │   └── notifications.py # Webhooks & email notifications
│   │
│   ├── tasks/
│   │   ├── daily.py         # Daily scheduled tasks
│   │   └── monthly.py       # Monthly scheduled tasks
│   │
│   └── api/
│       ├── routes.py        # Extended API endpoints
│       └── docs.py          # OpenAPI documentation
│
├── migrations/
│   ├── env.py               # Alembic environment
│   ├── script.py.mako       # Migration template
│   └── versions/            # Migration files
│
├── static/
│   ├── js/
│   │   ├── main.js          # Application entry point
│   │   ├── api.js           # API client
│   │   ├── ui.js            # UI components
│   │   ├── charts.js        # Analytics charts
│   │   └── utils.js         # Utility functions
│   ├── script.js            # Legacy JavaScript (deprecated)
│   └── styles.css           # Application styles
│
├── templates/
│   └── index.html           # Main template
│
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_github_api.py   # GitHub API tests
│   ├── test_database.py     # Database tests
│   └── test_routes.py       # API route tests
│
└── data/
    ├── github_tracker.db    # SQLite database
    ├── ignore_list.txt      # User ignore list
    └── .encryption_key      # Encryption key (gitignored)
```

## Key Design Decisions

### 1. GraphQL over REST
- More efficient data fetching (get exactly what we need)
- Fewer API calls (batch multiple queries)
- Better rate limit utilization

### 2. SQLite with WAL Mode
- No external database dependency
- WAL mode enables concurrent reads
- Portable - single file database

### 3. Database-backed Cache
- Persistent across restarts
- Queryable (unlike file cache)
- Supports complex filtering

### 4. Event Sourcing for History
- Complete audit trail
- Easy analytics generation
- Supports undo operations

### 5. Optional Authentication
- Disabled by default (localhost use)
- Environment variable configuration
- Session + API token support

## Performance Considerations

### Rate Limiting
- 100ms minimum between requests
- Exponential backoff on failures
- Rate limit cache (60s TTL)

### Connection Pooling
- 10 pool connections
- 20 max pool size
- Pre-ping connection validation

### Caching Strategy
- 15-minute sync interval
- Staleness detection
- Manual refresh available

### Database Optimization
- Strategic indexes
- 64MB query cache
- Batch inserts for sync
