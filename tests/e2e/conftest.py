"""End-to-end test configuration for azure-functions-durable-graph.

Tests in this directory require Azure Functions runtime or Azurite.
Run with: make test-e2e
"""

import os

import pytest


@pytest.fixture
def e2e_base_url():
    """Base URL for e2e tests. Set E2E_BASE_URL env var."""
    url = os.environ.get("E2E_BASE_URL")
    if not url:
        pytest.skip("E2E_BASE_URL not set")
    return url
