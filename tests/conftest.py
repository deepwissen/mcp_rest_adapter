import pytest
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def anyio_backend():
    """Use asyncio as the async backend for anyio."""
    return 'asyncio'

# Async test configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )

@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test."""
    # Reset any global variables that might affect tests
    from mcp_adapter.server import sessions
    sessions.clear()
    
    yield
    
    # Clean up after test
    sessions.clear()

# Test data fixtures
@pytest.fixture
def sample_customer_data():
    """Sample customer data for testing."""
    return {
        "id": "cust-test",
        "name": "Test Customer",
        "email": "test@example.com",
        "phone": "+1234567890",
        "status": "active",
        "created_at": "2024-03-01T10:00:00Z"
    }

@pytest.fixture
def sample_order_data():
    """Sample order data for testing."""
    return {
        "id": "order-test",
        "customer_id": "cust-test",
        "items": [
            {
                "product_id": "prod-1",
                "product_name": "Test Product",
                "quantity": 2,
                "unit_price": 25.99
            }
        ],
        "status": "pending",
        "total_amount": 51.98,
        "created_at": "2024-03-01T10:00:00Z",
        "updated_at": "2024-03-01T10:00:00Z"
    }

@pytest.fixture
def sample_product_data():
    """Sample product data for testing."""
    return {
        "id": "prod-test",
        "name": "Test Product",
        "sku": "TST-001",
        "quantity": 100,
        "price": 25.99,
        "status": "available",
        "updated_at": "2024-03-01T10:00:00Z"
    }

@pytest.fixture
def sample_mcp_request():
    """Sample MCP request for testing."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }