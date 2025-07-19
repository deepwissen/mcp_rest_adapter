import pytest
from fastapi.testclient import TestClient
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add the directories to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../mock-services'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from mock_customer_service import app as customer_app
from mcp_adapter.server import app as mcp_app

@pytest.fixture
def customer_client():
    """Test client for customer service"""
    return TestClient(customer_app)

@pytest.fixture
def mcp_client():
    """Test client for MCP adapter"""
    return TestClient(mcp_app)

class TestToolSystemIntegration:
    """Integration tests for the complete tool system"""
    
    def test_mcp_initialization_with_tools(self, mcp_client):
        """Test MCP initialization loads tools from OpenAPI specs"""
        # Mock the service discovery and OpenAPI loading
        with patch('mcp_adapter.server.service_discovery') as mock_discovery, \
             patch('mcp_adapter.server.openapi_loader') as mock_loader, \
             patch('mcp_adapter.server.http_client') as mock_http_client:
            
            # Mock healthy services
            mock_discovery.get_healthy_services.return_value = {"customer"}
            
            # Mock OpenAPI spec
            mock_spec = MagicMock()
            mock_spec.service_name = "customer"
            mock_spec.title = "Customer API"
            mock_spec.endpoints = [
                MagicMock(
                    path="/customers/{customer_id}",
                    method="GET",
                    operation_id="getCustomer",
                    summary="Get customer by ID",
                    description="Retrieve customer details",
                    parameters=[
                        {
                            "name": "customer_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Customer ID"
                        }
                    ],
                    request_body=None,
                    responses={"200": {"description": "Customer details"}},
                    security=[],
                    tags=["customers"]
                )
            ]
            mock_loader.get_spec.return_value = mock_spec
            mock_loader.get_all_specs.return_value = {"customer": mock_spec}
            
            # Mock HTTP client
            mock_http_client.initialize.return_value = None
            
            # Initialize MCP
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
            
            response = mcp_client.post("/mcp", json=initialize_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["jsonrpc"] == "2.0"
            assert data["id"] == 1
            assert "result" in data
            assert "capabilities" in data["result"]
    
    def test_tools_list_after_initialization(self, mcp_client):
        """Test that tools are available after initialization"""
        with patch('mcp_adapter.server.service_discovery') as mock_discovery, \
             patch('mcp_adapter.server.openapi_loader') as mock_loader, \
             patch('mcp_adapter.server.http_client') as mock_http_client:
            
            # Mock healthy services
            mock_discovery.get_healthy_services.return_value = {"customer"}
            
            # Mock OpenAPI spec with endpoint
            mock_spec = MagicMock()
            mock_spec.service_name = "customer"
            mock_spec.endpoints = [
                MagicMock(
                    path="/customers/{customer_id}",
                    method="GET",
                    operation_id="getCustomer",
                    summary="Get customer by ID",
                    description="Retrieve customer details",
                    parameters=[
                        {
                            "name": "customer_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    request_body=None,
                    responses={},
                    security=[],
                    tags=[]
                )
            ]
            mock_loader.get_spec.return_value = mock_spec
            mock_loader.get_all_specs.return_value = {"customer": mock_spec}
            
            # Mock HTTP client
            mock_http_client.initialize.return_value = None
            
            # First initialize
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
            
            init_response = mcp_client.post("/mcp", json=initialize_request)
            assert init_response.status_code == 200
            
            # Then list tools
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
            
            tools = data["result"]["tools"]
            assert len(tools) == 1
            assert tools[0]["name"] == "customer_getCustomer"
            assert tools[0]["description"] == "Get customer by ID. Retrieve customer details. Path parameters: customer_id"
            assert "inputSchema" in tools[0]
            assert tools[0]["inputSchema"]["type"] == "object"
            assert "customer_id" in tools[0]["inputSchema"]["properties"]
    
    def test_tool_execution_success(self, mcp_client):
        """Test successful tool execution"""
        with patch('mcp_adapter.server.service_discovery') as mock_discovery, \
             patch('mcp_adapter.server.openapi_loader') as mock_loader, \
             patch('mcp_adapter.server.http_client') as mock_http_client:
            
            # Mock healthy services
            mock_discovery.get_healthy_services.return_value = {"customer"}
            
            # Mock OpenAPI spec
            mock_spec = MagicMock()
            mock_spec.service_name = "customer"
            mock_spec.endpoints = [
                MagicMock(
                    path="/customers/{customer_id}",
                    method="GET",
                    operation_id="getCustomer",
                    summary="Get customer by ID",
                    description="Retrieve customer details",
                    parameters=[
                        {
                            "name": "customer_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    request_body=None,
                    responses={},
                    security=[],
                    tags=[]
                )
            ]
            mock_loader.get_spec.return_value = mock_spec
            mock_loader.get_all_specs.return_value = {"customer": mock_spec}
            
            # Mock HTTP client
            mock_http_client.initialize.return_value = None
            
            # Mock successful HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "cust-001",
                "name": "John Doe",
                "email": "john@example.com"
            }
            mock_http_client.get.return_value = mock_response
            
            # Initialize first
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
            
            init_response = mcp_client.post("/mcp", json=initialize_request)
            assert init_response.status_code == 200
            
            # Execute tool
            tool_call_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "customer_getCustomer",
                    "arguments": {
                        "customer_id": "cust-001"
                    }
                }
            }
            
            response = mcp_client.post("/mcp", json=tool_call_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["jsonrpc"] == "2.0"
            assert data["id"] == 3
            assert "result" in data
            
            result = data["result"]
            assert result["isError"] is False
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"
            
            # Verify the HTTP client was called correctly
            mock_http_client.get.assert_called_once_with(
                "customer",
                "/customers/cust-001",
                params={}
            )
            
            # Verify the response contains the customer data
            response_text = result["content"][0]["text"]
            response_data = json.loads(response_text)
            assert response_data["id"] == "cust-001"
            assert response_data["name"] == "John Doe"
    
    def test_tool_execution_tool_not_found(self, mcp_client):
        """Test tool execution with non-existent tool"""
        with patch('mcp_adapter.server.service_discovery') as mock_discovery, \
             patch('mcp_adapter.server.openapi_loader') as mock_loader, \
             patch('mcp_adapter.server.http_client') as mock_http_client:
            
            # Mock empty services
            mock_discovery.get_healthy_services.return_value = set()
            mock_loader.get_all_specs.return_value = {}
            mock_http_client.initialize.return_value = None
            
            # Initialize first
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
            
            init_response = mcp_client.post("/mcp", json=initialize_request)
            assert init_response.status_code == 200
            
            # Try to execute non-existent tool
            tool_call_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "nonexistent_tool",
                    "arguments": {}
                }
            }
            
            response = mcp_client.post("/mcp", json=tool_call_request)
            assert response.status_code == 200
            
            data = response.json()
            assert data["jsonrpc"] == "2.0"
            assert data["id"] == 3
            assert "result" in data
            
            result = data["result"]
            assert result["isError"] is True
            assert "Tool not found" in result["content"][0]["text"]
    
    def test_tool_execution_validation_error(self, mcp_client):
        """Test tool execution with validation error"""
        with patch('mcp_adapter.server.service_discovery') as mock_discovery, \
             patch('mcp_adapter.server.openapi_loader') as mock_loader, \
             patch('mcp_adapter.server.http_client') as mock_http_client:
            
            # Mock healthy services
            mock_discovery.get_healthy_services.return_value = {"customer"}
            
            # Mock OpenAPI spec
            mock_spec = MagicMock()
            mock_spec.service_name = "customer"
            mock_spec.endpoints = [
                MagicMock(
                    path="/customers/{customer_id}",
                    method="GET",
                    operation_id="getCustomer",
                    summary="Get customer by ID",
                    description="Retrieve customer details",
                    parameters=[
                        {
                            "name": "customer_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    request_body=None,
                    responses={},
                    security=[],
                    tags=[]
                )
            ]
            mock_loader.get_spec.return_value = mock_spec
            mock_loader.get_all_specs.return_value = {"customer": mock_spec}
            
            # Mock HTTP client
            mock_http_client.initialize.return_value = None
            
            # Initialize first
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
            
            init_response = mcp_client.post("/mcp", json=initialize_request)
            assert init_response.status_code == 200
            
            # Execute tool with missing required parameter
            tool_call_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "customer_getCustomer",
                    "arguments": {}  # Missing required customer_id
                }
            }
            
            response = mcp_client.post("/mcp", json=tool_call_request)
            assert response.status_code == 200
            
            data = response.json()
            result = data["result"]
            assert result["isError"] is True
            assert "Missing required parameter: customer_id" in result["content"][0]["text"]
    
    def test_health_check_with_tools(self, mcp_client):
        """Test health check endpoint after tool initialization"""
        with patch('mcp_adapter.server.service_discovery') as mock_discovery, \
             patch('mcp_adapter.server.openapi_loader') as mock_loader, \
             patch('mcp_adapter.server.http_client') as mock_http_client:
            
            # Mock healthy services
            mock_discovery.get_healthy_services.return_value = {"customer"}
            
            # Mock OpenAPI spec
            mock_spec = MagicMock()
            mock_spec.service_name = "customer"
            mock_spec.endpoints = [MagicMock()]  # One endpoint
            mock_loader.get_spec.return_value = mock_spec
            mock_loader.get_all_specs.return_value = {"customer": mock_spec}
            
            # Mock HTTP client
            mock_http_client.initialize.return_value = None
            
            # Initialize MCP server
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
            
            init_response = mcp_client.post("/mcp", json=initialize_request)
            assert init_response.status_code == 200
            
            # Check health
            health_response = mcp_client.get("/health")
            assert health_response.status_code == 200
            
            health_data = health_response.json()
            assert health_data["status"] == "healthy"
            assert health_data["service"] == "mcp-adapter"
            assert "details" in health_data
            assert health_data["details"]["tools_available"] == 1
            assert health_data["details"]["healthy_services"] == 1