"""
OpenAPI/Swagger documentation for GitHub Followers Tracker API.
"""
from flask import Blueprint, jsonify, render_template_string

api_docs = Blueprint('api_docs', __name__)

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "GitHub Followers Tracker API",
        "description": "API for tracking GitHub followers, managing follow/unfollow actions, and analytics.",
        "version": "2.0.0",
        "contact": {
            "name": "GitHub Followers Tracker"
        },
        "license": {
            "name": "MIT"
        }
    },
    "servers": [
        {
            "url": "/",
            "description": "Local server"
        }
    ],
    "tags": [
        {"name": "Data", "description": "Fetch follower/following data"},
        {"name": "Actions", "description": "Follow/unfollow actions"},
        {"name": "Analytics", "description": "Statistics and analytics"},
        {"name": "Management", "description": "User management (ignore list, whitelist, tags)"},
        {"name": "Accounts", "description": "Multi-account management"},
        {"name": "Webhooks", "description": "Webhook configuration"},
        {"name": "Scheduling", "description": "Automated task scheduling"},
        {"name": "Export", "description": "Data export"},
        {"name": "Notifications", "description": "Notification settings"}
    ],
    "paths": {
        "/": {
            "get": {
                "summary": "Dashboard",
                "description": "Render the main dashboard page",
                "tags": ["Data"],
                "responses": {
                    "200": {
                        "description": "HTML dashboard page",
                        "content": {"text/html": {}}
                    }
                }
            }
        },
        "/get_data": {
            "get": {
                "summary": "Get follower/following data",
                "description": "Fetch various types of follower and following data",
                "tags": ["Data"],
                "parameters": [
                    {
                        "name": "type",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": ["followers", "following", "new_followers", "unfollowers",
                                    "not_following_back", "suggested_users", "users_more_following"]
                        },
                        "description": "Type of data to fetch"
                    },
                    {
                        "name": "page",
                        "in": "query",
                        "schema": {"type": "integer", "default": 1},
                        "description": "Page number for pagination"
                    },
                    {
                        "name": "per_page",
                        "in": "query",
                        "schema": {"type": "integer", "default": 50, "maximum": 100},
                        "description": "Items per page"
                    },
                    {
                        "name": "search",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Search filter for usernames"
                    },
                    {
                        "name": "sort",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["username", "followers", "following", "date"],
                            "default": "username"
                        },
                        "description": "Sort field"
                    },
                    {
                        "name": "order",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["asc", "desc"], "default": "asc"},
                        "description": "Sort order"
                    },
                    {
                        "name": "account_id",
                        "in": "query",
                        "schema": {"type": "integer"},
                        "description": "Account ID (for multi-account support)"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "data": {"type": "array", "items": {"$ref": "#/components/schemas/User"}},
                                        "pagination": {"$ref": "#/components/schemas/Pagination"}
                                    }
                                }
                            }
                        }
                    },
                    "400": {"description": "Invalid data type"},
                    "500": {"description": "Server error"}
                }
            }
        },
        "/follow/{username}": {
            "post": {
                "summary": "Follow a user",
                "tags": ["Actions"],
                "parameters": [
                    {
                        "name": "username",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "maxLength": 39}
                    }
                ],
                "responses": {
                    "200": {"description": "Successfully followed"},
                    "400": {"description": "Invalid username"},
                    "500": {"description": "Failed to follow"}
                }
            }
        },
        "/unfollow/{username}": {
            "post": {
                "summary": "Unfollow a user",
                "tags": ["Actions"],
                "parameters": [
                    {
                        "name": "username",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "maxLength": 39}
                    }
                ],
                "responses": {
                    "200": {"description": "Successfully unfollowed"},
                    "400": {"description": "Invalid username"},
                    "500": {"description": "Failed to unfollow"}
                }
            }
        },
        "/bulk_follow": {
            "post": {
                "summary": "Follow multiple users",
                "tags": ["Actions"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "usernames": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "maxItems": 100
                                    },
                                    "dry_run": {"type": "boolean", "default": False}
                                },
                                "required": ["usernames"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Results for each user",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "message": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/bulk_unfollow": {
            "post": {
                "summary": "Unfollow multiple users",
                "tags": ["Actions"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "usernames": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "maxItems": 100
                                    },
                                    "dry_run": {"type": "boolean", "default": False}
                                },
                                "required": ["usernames"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Results for each user"}
                }
            }
        },
        "/check_follow": {
            "get": {
                "summary": "Check if user follows you",
                "tags": ["Data"],
                "parameters": [
                    {
                        "name": "username",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Follow status",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string"},
                                        "follows_you": {"type": "boolean"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/ignore-list": {
            "get": {
                "summary": "Get ignore list",
                "tags": ["Management"],
                "responses": {
                    "200": {
                        "description": "List of ignored usernames",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ignore_list": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "summary": "Add to ignore list",
                "tags": ["Management"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"username": {"type": "string"}},
                                "required": ["username"]
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "Updated ignore list"}}
            },
            "delete": {
                "summary": "Remove from ignore list",
                "tags": ["Management"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"username": {"type": "string"}},
                                "required": ["username"]
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "Updated ignore list"}}
            }
        },
        "/api/whitelist": {
            "get": {
                "summary": "Get whitelist",
                "tags": ["Management"],
                "responses": {
                    "200": {
                        "description": "List of whitelisted usernames"
                    }
                }
            },
            "post": {
                "summary": "Add to whitelist",
                "tags": ["Management"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"username": {"type": "string"}},
                                "required": ["username"]
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "Updated whitelist"}}
            },
            "delete": {
                "summary": "Remove from whitelist",
                "tags": ["Management"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"username": {"type": "string"}},
                                "required": ["username"]
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "Updated whitelist"}}
            }
        },
        "/api/user/{username}/metadata": {
            "get": {
                "summary": "Get user metadata",
                "tags": ["Management"],
                "parameters": [
                    {"name": "username", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {
                        "description": "User metadata",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UserMetadata"}
                            }
                        }
                    }
                }
            },
            "put": {
                "summary": "Update user metadata",
                "tags": ["Management"],
                "parameters": [
                    {"name": "username", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/UserMetadataUpdate"}
                        }
                    }
                },
                "responses": {"200": {"description": "Updated metadata"}}
            }
        },
        "/api/tags": {
            "get": {
                "summary": "Get all tags",
                "tags": ["Management"],
                "responses": {
                    "200": {
                        "description": "List of all tags with user counts"
                    }
                }
            }
        },
        "/api/tags/{tag}/users": {
            "get": {
                "summary": "Get users with a specific tag",
                "tags": ["Management"],
                "parameters": [
                    {"name": "tag", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {"description": "List of users with the tag"}}
            }
        },
        "/api/analytics": {
            "get": {
                "summary": "Get analytics data",
                "tags": ["Analytics"],
                "parameters": [
                    {
                        "name": "days",
                        "in": "query",
                        "schema": {"type": "integer", "default": 30, "maximum": 365},
                        "description": "Number of days of history"
                    },
                    {
                        "name": "account_id",
                        "in": "query",
                        "schema": {"type": "integer"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Analytics data",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Analytics"}
                            }
                        }
                    }
                }
            }
        },
        "/api/analytics/history": {
            "get": {
                "summary": "Get follower history events",
                "tags": ["Analytics"],
                "parameters": [
                    {"name": "days", "in": "query", "schema": {"type": "integer", "default": 30}},
                    {"name": "event_type", "in": "query", "schema": {"type": "string"}},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 50}}
                ],
                "responses": {"200": {"description": "History events"}}
            }
        },
        "/api/rate-limit": {
            "get": {
                "summary": "Get GitHub API rate limit status",
                "tags": ["Analytics"],
                "responses": {
                    "200": {
                        "description": "Rate limit information",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "limit": {"type": "integer"},
                                        "remaining": {"type": "integer"},
                                        "reset_at": {"type": "string", "format": "date-time"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/export": {
            "get": {
                "summary": "Export data",
                "tags": ["Export"],
                "parameters": [
                    {
                        "name": "format",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "enum": ["json", "csv"]}
                    },
                    {
                        "name": "type",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": ["followers", "following", "history", "analytics", "all"]
                        }
                    },
                    {
                        "name": "days",
                        "in": "query",
                        "schema": {"type": "integer", "default": 30}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Exported data file",
                        "content": {
                            "application/json": {},
                            "text/csv": {}
                        }
                    }
                }
            }
        },
        "/api/accounts": {
            "get": {
                "summary": "List all accounts",
                "tags": ["Accounts"],
                "responses": {
                    "200": {
                        "description": "List of configured accounts"
                    }
                }
            },
            "post": {
                "summary": "Add a new account",
                "tags": ["Accounts"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string"},
                                    "token": {"type": "string"},
                                    "is_default": {"type": "boolean"}
                                },
                                "required": ["username", "token"]
                            }
                        }
                    }
                },
                "responses": {"201": {"description": "Account created"}}
            }
        },
        "/api/accounts/{account_id}": {
            "get": {
                "summary": "Get account details",
                "tags": ["Accounts"],
                "parameters": [
                    {"name": "account_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "Account details"}}
            },
            "put": {
                "summary": "Update account",
                "tags": ["Accounts"],
                "parameters": [
                    {"name": "account_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "token": {"type": "string"},
                                    "is_active": {"type": "boolean"},
                                    "is_default": {"type": "boolean"}
                                }
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "Account updated"}}
            },
            "delete": {
                "summary": "Delete account",
                "tags": ["Accounts"],
                "parameters": [
                    {"name": "account_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "Account deleted"}}
            }
        },
        "/api/accounts/{account_id}/switch": {
            "post": {
                "summary": "Switch active account",
                "tags": ["Accounts"],
                "parameters": [
                    {"name": "account_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "Account switched"}}
            }
        },
        "/api/webhooks": {
            "get": {
                "summary": "List webhooks",
                "tags": ["Webhooks"],
                "responses": {"200": {"description": "List of webhooks"}}
            },
            "post": {
                "summary": "Create webhook",
                "tags": ["Webhooks"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/WebhookCreate"}
                        }
                    }
                },
                "responses": {"201": {"description": "Webhook created"}}
            }
        },
        "/api/webhooks/{webhook_id}": {
            "put": {
                "summary": "Update webhook",
                "tags": ["Webhooks"],
                "parameters": [
                    {"name": "webhook_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "Webhook updated"}}
            },
            "delete": {
                "summary": "Delete webhook",
                "tags": ["Webhooks"],
                "parameters": [
                    {"name": "webhook_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "Webhook deleted"}}
            }
        },
        "/api/webhooks/{webhook_id}/test": {
            "post": {
                "summary": "Test webhook",
                "tags": ["Webhooks"],
                "parameters": [
                    {"name": "webhook_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "Test result"}}
            }
        },
        "/api/schedule": {
            "get": {
                "summary": "Get schedule configuration",
                "tags": ["Scheduling"],
                "responses": {"200": {"description": "Schedule configurations"}}
            },
            "put": {
                "summary": "Update schedule configuration",
                "tags": ["Scheduling"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ScheduleConfig"}
                        }
                    }
                },
                "responses": {"200": {"description": "Schedule updated"}}
            }
        },
        "/api/schedule/run": {
            "post": {
                "summary": "Run scheduled task manually",
                "tags": ["Scheduling"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "task": {"type": "string", "enum": ["daily_follow", "monthly_unfollow"]},
                                    "dry_run": {"type": "boolean", "default": False}
                                },
                                "required": ["task"]
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "Task result"}}
            }
        },
        "/api/actions/history": {
            "get": {
                "summary": "Get action history",
                "tags": ["Actions"],
                "parameters": [
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 50}}
                ],
                "responses": {"200": {"description": "Action history"}}
            }
        },
        "/api/actions/{action_id}/undo": {
            "post": {
                "summary": "Undo an action",
                "tags": ["Actions"],
                "parameters": [
                    {"name": "action_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Action undone"},
                    "400": {"description": "Cannot undo this action"},
                    "404": {"description": "Action not found"}
                }
            }
        },
        "/api/notifications/config": {
            "get": {
                "summary": "Get notification configuration",
                "tags": ["Notifications"],
                "responses": {"200": {"description": "Notification config"}}
            },
            "put": {
                "summary": "Update notification configuration",
                "tags": ["Notifications"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/NotificationConfig"}
                        }
                    }
                },
                "responses": {"200": {"description": "Config updated"}}
            }
        },
        "/api/follow-back-deadlines": {
            "get": {
                "summary": "Get users with follow-back deadlines",
                "tags": ["Management"],
                "responses": {"200": {"description": "Users with deadlines"}}
            }
        },
        "/api/follow-back-deadlines/{username}": {
            "put": {
                "summary": "Set follow-back deadline for a user",
                "tags": ["Management"],
                "parameters": [
                    {"name": "username", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "deadline_days": {"type": "integer", "minimum": 1, "maximum": 365}
                                },
                                "required": ["deadline_days"]
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "Deadline set"}}
            },
            "delete": {
                "summary": "Remove follow-back deadline",
                "tags": ["Management"],
                "parameters": [
                    {"name": "username", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {"description": "Deadline removed"}}
            }
        }
    },
    "components": {
        "schemas": {
            "User": {
                "type": "object",
                "properties": {
                    "login": {"type": "string"},
                    "followers": {"type": "integer"},
                    "following": {"type": "integer"},
                    "avatar_url": {"type": "string"},
                    "bio": {"type": "string"},
                    "public_repos": {"type": "integer"}
                }
            },
            "UserMetadata": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "is_whitelisted": {"type": "boolean"},
                    "is_ignored": {"type": "boolean"},
                    "notes": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "followed_at": {"type": "string", "format": "date-time"},
                    "follow_back_deadline": {"type": "string", "format": "date-time"}
                }
            },
            "UserMetadataUpdate": {
                "type": "object",
                "properties": {
                    "notes": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "is_whitelisted": {"type": "boolean"},
                    "is_ignored": {"type": "boolean"}
                }
            },
            "Pagination": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer"},
                    "per_page": {"type": "integer"},
                    "total": {"type": "integer"},
                    "total_pages": {"type": "integer"}
                }
            },
            "Analytics": {
                "type": "object",
                "properties": {
                    "period_days": {"type": "integer"},
                    "snapshots": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string", "format": "date"},
                                "followers": {"type": "integer"},
                                "following": {"type": "integer"}
                            }
                        }
                    },
                    "summary": {
                        "type": "object",
                        "properties": {
                            "total_growth": {"type": "integer"},
                            "growth_rate_percent": {"type": "number"},
                            "total_gained": {"type": "integer"},
                            "total_lost": {"type": "integer"}
                        }
                    }
                }
            },
            "WebhookCreate": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "url": {"type": "string", "format": "uri"},
                    "secret": {"type": "string"},
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["all", "follower_gained", "follower_lost", "milestone_reached",
                                    "daily_digest", "weekly_digest"]
                        }
                    }
                },
                "required": ["name", "url"]
            },
            "ScheduleConfig": {
                "type": "object",
                "properties": {
                    "task_name": {"type": "string"},
                    "is_enabled": {"type": "boolean"},
                    "hour": {"type": "integer", "minimum": 0, "maximum": 23},
                    "minute": {"type": "integer", "minimum": 0, "maximum": 59},
                    "day_of_month": {"type": "integer", "minimum": 1, "maximum": 31},
                    "dry_run": {"type": "boolean"}
                }
            },
            "NotificationConfig": {
                "type": "object",
                "properties": {
                    "email_enabled": {"type": "boolean"},
                    "email_address": {"type": "string", "format": "email"},
                    "smtp_host": {"type": "string"},
                    "smtp_port": {"type": "integer"},
                    "smtp_username": {"type": "string"},
                    "smtp_password": {"type": "string"},
                    "notify_on_follow": {"type": "boolean"},
                    "notify_on_unfollow": {"type": "boolean"},
                    "notify_on_milestone": {"type": "boolean"},
                    "daily_digest_enabled": {"type": "boolean"},
                    "weekly_digest_enabled": {"type": "boolean"},
                    "milestone_thresholds": {
                        "type": "array",
                        "items": {"type": "integer"}
                    }
                }
            }
        }
    }
}


SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>GitHub Followers Tracker API</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body { margin: 0; padding: 0; }
        .swagger-ui .topbar { display: none; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({
            url: "/api/docs/openapi.json",
            dom_id: '#swagger-ui',
            presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
            layout: "BaseLayout"
        });
    </script>
</body>
</html>
"""


@api_docs.route('/api/docs')
def swagger_ui():
    """Render Swagger UI."""
    return render_template_string(SWAGGER_UI_HTML)


@api_docs.route('/api/docs/openapi.json')
def openapi_spec():
    """Return OpenAPI specification."""
    return jsonify(OPENAPI_SPEC)
