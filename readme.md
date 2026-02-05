# Box Mock API

A mock implementation of the Box API for testing purposes. Built with Flask and SQLite with **identity-based isolation** for parallel test execution. Browse files, users, and folders for each identity at `/_browse`.

## Getting the Image

Pull from Docker Hub:

```bash
docker pull coletpa/box-mock:latest
docker run -p 8888:8888 coletpa/box-mock:latest
```

Or build locally:

```bash
docker build -t box-mock .
docker run -p 8888:8888 box-mock
```

## Identity Isolation

Each request can specify an `Identity` in the Authorization header to isolate data:

```
Authorization: Bearer mock-token; Identity=worker1; User-ID=123
```

- Each identity gets its own SQLite database and file storage under `/data/{identity}/`
- Requests without an identity default to `"default"`
- The `/_browse` page shows all identities and their data

## Using with Box SDK

To use box-mock with the official `box-sdk-gen` Python SDK, create a custom auth class that includes the identity header:

```python
from box_sdk_gen import BoxClient
from box_sdk_gen.networking.base_urls import BaseUrls
from box_sdk_gen.networking.network import NetworkSession


class MockBoxAuth:
    """No-op auth for box-mock that includes worker identity for test isolation."""

    def __init__(self, identity: str = "default", user_id: str = "default"):
        self.identity = identity
        self.user_id = user_id

    def with_user_subject(self, user_id: str):
        return MockBoxAuth(identity=self.identity, user_id=user_id)

    def retrieve_authorization_header(self, network_session=None):
        return f"Bearer mock-token; Identity={self.identity}; User-ID={self.user_id}"

    def refresh_token(self, network_session=None):
        pass


def get_mock_box_client(mock_url: str, identity: str = "default") -> BoxClient:
    """Create a Box client that connects to box-mock."""
    base_urls = BaseUrls(
        base_url=mock_url,
        upload_url=mock_url,
        oauth2_url=mock_url,
    )
    network_session = NetworkSession(base_urls=base_urls)
    return BoxClient(auth=MockBoxAuth(identity=identity), network_session=network_session)


# Usage
client = get_mock_box_client("http://localhost:8888", identity="test-worker-1")
folders = client.folders.get_folder_items("0")
```

## Development

```bash
./run quality        # Lint and format
```
