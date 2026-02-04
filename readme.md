# Box Mock API

A mock implementation of the Box API for testing purposes. Built with Flask and SQLite with **identity-based isolation** for parallel test execution.

## Identity Isolation

Each request can specify an `Identity` in the Authorization header to isolate data:

```
Authorization: Bearer mock-token; Identity=worker1; User-ID=123
```

- Each identity gets its own SQLite database and file storage under `/data/{identity}/`
- Requests without an identity default to `"default"`
- The `/_browse` page shows all identities and their data

## Running

### Docker

```bash
docker build -t box-mock .
docker run -p 8888:8888 box-mock
```

## Endpoints

| Route | Description |
|-------|-------------|
| `/health` | Health check |
| `/_browse` | HTML view of all identities and their data |
| `/_reset` | Reset data for an identity (POST with `{"identity": "..."}`) |
| `/2.0/users` | User management |
| `/2.0/folders` | Folder operations |
| `/2.0/files` | File upload/download |
| `/2.0/collaborations` | Collaboration management |
| `/2.0/sign_requests` | Box Sign requests |

## Module Structure

```
box_mock/
├── db.py           # Identity-based SQLAlchemy session management
├── hooks.py        # Flask request hooks (session setup/teardown)
├── identity.py     # Identity extraction from headers
├── models.py       # SQLAlchemy models (Folder, File, User, etc.)
└── routes/
    ├── admin.py         # /_browse, /_reset, /health
    ├── collaborations.py
    ├── files.py
    ├── folders.py
    ├── sign_requests.py
    └── users.py
```

## Development

```bash
# Lint and format
ruff check --fix && ruff format

# Check only
ruff check && ruff format --check
```
