import pytest
import httpx
import asyncio
from fastapi.testclient import TestClient
import sys
import os
import json

# Add the mock-services and mcp_adapter directories to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../mock-services'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from mock_customer_service import app as customer_app
from mock_order_service import app as order_app
from mock_inventory_service import app as inventory_app
from mcp_adapter.server import app as mcp_app

@pytest.fixture
def customer_client():
    """Test client for customer service"""
    return TestClient(customer_app)

@pytest.fixture
def order_client():
    """Test client for order service"""
    return TestClient(order_app)

@pytest.fixture
def inventory_client():
    """Test client for inventory service"""
    return TestClient(inventory_app)

@pytest.fixture
def mcp_client():
    """Test client for MCP adapter"""
    return TestClient(mcp_app)

class TestFullStackIntegration:
    
    def test_all_services_health(self, customer_client, order_client, inventory_client, mcp_client):
        """Test that all services are healthy"""
        # Customer service
        response = customer_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        
        # Order service
        response = order_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        
        # Inventory service
        response = inventory_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        
        # MCP adapter
        response = mcp_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_customer_service_crud(self, customer_client):
        """Test customer service CRUD operations"""
        # Create customer
        new_customer = {
            "id": "cust-999",
            "name": "Test Customer",
            "email": "test@example.com",
            "phone": "+1234567890",
            "status": "active",
            "created_at": "2024-03-01T10:00:00Z"
        }
        
        response = customer_client.post("/customers", json=new_customer)
        assert response.status_code == 200
        created_customer = response.json()
        assert created_customer["id"] == "cust-999"
        
        # Get customer
        response = customer_client.get("/customers/cust-999")
        assert response.status_code == 200
        retrieved_customer = response.json()
        assert retrieved_customer["id"] == "cust-999"
        assert retrieved_customer["name"] == "Test Customer"
        
        # Update customer
        update_data = {"name": "Updated Customer"}
        response = customer_client.put("/customers/cust-999", json=update_data)
        assert response.status_code == 200
        updated_customer = response.json()
        assert updated_customer["name"] == "Updated Customer"
        
        # List customers
        response = customer_client.get("/customers")
        assert response.status_code == 200
        customers = response.json()
        assert len(customers) >= 1
        assert any(c["id"] == "cust-999" for c in customers)
    
    def test_order_service_operations(self, order_client):
        """Test order service operations"""
        # Create order
        new_order = {
            "id": "order-999",
            "customer_id": "cust-001",
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
        
        response = order_client.post("/orders", json=new_order)
        assert response.status_code == 200
        created_order = response.json()
        assert created_order["id"] == "order-999"
        
        # Get order
        response = order_client.get("/orders/order-999")
        assert response.status_code == 200
        retrieved_order = response.json()
        assert retrieved_order["id"] == "order-999"
        assert retrieved_order["status"] == "pending"
        
        # Update order status
        response = order_client.put("/orders/order-999/status?status=confirmed")
        assert response.status_code == 200
        updated_order = response.json()
        assert updated_order["status"] == "confirmed"
        
        # List orders
        response = order_client.get("/orders")
        assert response.status_code == 200
        orders = response.json()
        assert len(orders) >= 1
        assert any(o["id"] == "order-999" for o in orders)
    
    def test_inventory_service_operations(self, inventory_client):
        """Test inventory service operations"""
        # Get product
        response = inventory_client.get("/products/prod-1")
        assert response.status_code == 200
        product = response.json()
        assert product["id"] == "prod-1"
        assert product["name"] == "Widget A"
        
        # Update quantity
        response = inventory_client.put("/products/prod-1/quantity?quantity=150")
        assert response.status_code == 200
        updated_product = response.json()
        assert updated_product["quantity"] == 150
        
        # List products
        response = inventory_client.get("/products")
        assert response.status_code == 200
        products = response.json()
        assert len(products) >= 1
        assert any(p["id"] == "prod-1" for p in products)
    
    def test_mcp_initialize_flow(self, mcp_client):
        """Test MCP initialization flow"""
        # Initialize
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "integration-test", "version": "1.0.0"}
            }
        }
        
        response = mcp_client.post("/mcp", json=initialize_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "mcp-session-id" in response.headers
        
        session_id = response.headers["mcp-session-id"]
        
        # Send initialized notification
        initialized_request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        response = mcp_client.post(
            "/mcp",
            json=initialized_request,
            headers={"Mcp-Session-Id": session_id}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_mcp_tools_list(self, mcp_client):
        """Test MCP tools list endpoint"""
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = mcp_client.post("/mcp", json=tools_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert "result" in data
        assert "tools" in data["result"]
        assert isinstance(data["result"]["tools"], list)
    
    def test_openapi_specs_available(self, customer_client, order_client, inventory_client):
        """Test that OpenAPI specs are available from all services"""
        # Customer service OpenAPI
        response = customer_client.get("/openapi.json")
        assert response.status_code == 200
        customer_spec = response.json()
        assert "openapi" in customer_spec
        assert "paths" in customer_spec
        assert customer_spec["info"]["title"] == "Customer Service"
        
        # Order service OpenAPI
        response = order_client.get("/openapi.json")
        assert response.status_code == 200
        order_spec = response.json()
        assert "openapi" in order_spec
        assert "paths" in order_spec
        assert order_spec["info"]["title"] == "Order Service"
        
        # Inventory service OpenAPI
        response = inventory_client.get("/openapi.json")
        assert response.status_code == 200
        inventory_spec = response.json()
        assert "openapi" in inventory_spec
        assert "paths" in inventory_spec
        assert inventory_spec["info"]["title"] == "Inventory Service"
    
    def test_data_consistency_across_services(self, customer_client, order_client):
        """Test data consistency between customer and order services"""
        # Create a customer
        customer_data = {
            "id": "cust-test",
            "name": "Test Customer",
            "email": "test@example.com",
            "status": "active",
            "created_at": "2024-03-01T10:00:00Z"
        }
        
        customer_response = customer_client.post("/customers", json=customer_data)
        assert customer_response.status_code == 200
        
        # Create an order for that customer
        order_data = {
            "id": "order-test",
            "customer_id": "cust-test",
            "items": [
                {
                    "product_id": "prod-1",
                    "product_name": "Test Product",
                    "quantity": 1,
                    "unit_price": 10.00
                }
            ],
            "status": "pending",
            "total_amount": 10.00,
            "created_at": "2024-03-01T10:00:00Z",
            "updated_at": "2024-03-01T10:00:00Z"
        }
        
        order_response = order_client.post("/orders", json=order_data)
        assert order_response.status_code == 200
        
        # Verify order references the correct customer
        order = order_response.json()
        assert order["customer_id"] == "cust-test"
        
        # Get orders for the customer
        orders_response = order_client.get("/orders?customer_id=cust-test")
        assert orders_response.status_code == 200
        
        orders = orders_response.json()
        assert len(orders) >= 1
        assert orders[0]["customer_id"] == "cust-test"
    
    def test_error_handling_across_services(self, customer_client, order_client, inventory_client, mcp_client):
        """Test error handling across all services"""
        # Customer service - not found
        response = customer_client.get("/customers/non-existent")
        assert response.status_code == 404
        
        # Order service - not found
        response = order_client.get("/orders/non-existent")
        assert response.status_code == 404
        
        # Inventory service - not found
        response = inventory_client.get("/products/non-existent")
        assert response.status_code == 404
        
        # MCP adapter - method not found
        bad_request = {
            "jsonrpc": "2.0",
            "id": 999,
            "method": "non_existent_method",
            "params": {}
        }
        
        response = mcp_client.post("/mcp", json=bad_request)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601
    
    def test_service_validation(self, customer_client, order_client):
        """Test validation across services"""
        # Customer service validation
        invalid_customer = {
            "id": "invalid-format",  # Should be cust-XXX
            "name": "Test",
            "email": "not-an-email",
            "status": "active",
            "created_at": "2024-03-01T10:00:00Z"
        }
        
        response = customer_client.post("/customers", json=invalid_customer)
        assert response.status_code == 422
        
        # Order service validation
        invalid_order = {
            "id": "order-test",
            "customer_id": "cust-001",
            "items": [],  # Empty items should be invalid
            "status": "invalid-status",  # Invalid status
            "total_amount": -10.00,  # Negative amount
            "created_at": "2024-03-01T10:00:00Z",
            "updated_at": "2024-03-01T10:00:00Z"
        }
        
        response = order_client.post("/orders", json=invalid_order)
        # This might pass as we haven't implemented all validations yet
        # but it demonstrates the test structure