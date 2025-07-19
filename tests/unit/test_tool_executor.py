import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import sys
import os

# Add the mcp_adapter directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from mcp_adapter.tool_executor import ToolExecutor
from mcp_adapter.tool_generator import MCPTool
from mcp_adapter.request_translator import RequestTranslator

@pytest.fixture
def mock_tool_generator():
    """Mock tool generator"""
    generator = MagicMock()
    
    # Sample tool
    sample_tool = MCPTool(
        name="customer_getCustomer",
        description="Get customer by ID",
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "include_orders": {"type": "boolean", "default": False}
            },
            "required": ["customer_id"]
        },
        service_name="customer",
        endpoint_path="/customers/{customer_id}",
        http_method="GET",
        parameters=[
            {"name": "customer_id", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "include_orders", "in": "query", "required": False, "schema": {"type": "boolean"}}
        ]
    )
    
    generator.get_tool.return_value = sample_tool
    generator.get_all_tools.return_value = {"customer_getCustomer": sample_tool}
    
    return generator

@pytest.fixture
def mock_http_client():
    """Mock HTTP client"""
    client = MagicMock()
    
    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "cust-001",
        "name": "John Doe",
        "email": "john@example.com"
    }
    mock_response.text = '{"id": "cust-001", "name": "John Doe", "email": "john@example.com"}'
    
    client.get = AsyncMock(return_value=mock_response)
    client.post = AsyncMock(return_value=mock_response)
    client.put = AsyncMock(return_value=mock_response)
    client.delete = AsyncMock(return_value=mock_response)
    client.patch = AsyncMock(return_value=mock_response)
    
    return client

@pytest.fixture
def request_translator():
    """Request translator instance"""
    return RequestTranslator()

@pytest.fixture
def tool_executor(mock_tool_generator, mock_http_client, request_translator):
    """Tool executor instance"""
    return ToolExecutor(mock_tool_generator, mock_http_client, request_translator)

@pytest.mark.asyncio
class TestToolExecutor:
    
    async def test_execute_tool_success(self, tool_executor, mock_http_client):
        """Test successful tool execution"""
        result = await tool_executor.execute_tool("customer_getCustomer", {"customer_id": "cust-001"})
        
        # Should call HTTP client
        mock_http_client.get.assert_called_once_with(
            "customer", 
            "/customers/cust-001", 
            params={}
        )
        
        # Should return MCP response
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "cust-001" in result["content"][0]["text"]
        assert result["isError"] is False
    
    async def test_execute_tool_with_query_params(self, tool_executor, mock_http_client):
        """Test tool execution with query parameters"""
        result = await tool_executor.execute_tool("customer_getCustomer", {
            "customer_id": "cust-001",
            "include_orders": True
        })
        
        # Should call HTTP client with query params
        mock_http_client.get.assert_called_once_with(
            "customer", 
            "/customers/cust-001", 
            params={"include_orders": True}
        )
        
        assert result["isError"] is False
    
    async def test_execute_tool_not_found(self, tool_executor, mock_tool_generator):
        """Test executing non-existent tool"""
        mock_tool_generator.get_tool.return_value = None
        
        result = await tool_executor.execute_tool("nonexistent_tool", {})
        
        assert result["isError"] is True
        assert "Tool not found" in result["content"][0]["text"]
        assert result["_meta"]["error_code"] == 404
    
    async def test_execute_tool_missing_required_param(self, tool_executor):
        """Test executing tool with missing required parameter"""
        result = await tool_executor.execute_tool("customer_getCustomer", {})
        
        assert result["isError"] is True
        assert "Missing required parameter: customer_id" in result["content"][0]["text"]
        assert result["_meta"]["error_code"] == 400
    
    async def test_execute_tool_invalid_param_type(self, tool_executor):
        """Test executing tool with invalid parameter type"""
        result = await tool_executor.execute_tool("customer_getCustomer", {
            "customer_id": "cust-001",
            "include_orders": "not_boolean"  # Should be boolean
        })
        
        assert result["isError"] is True
        assert "Invalid type for parameter 'include_orders'" in result["content"][0]["text"]
    
    async def test_execute_tool_http_error(self, tool_executor, mock_http_client):
        """Test handling HTTP errors"""
        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Customer not found"
        
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
        mock_http_client.get.side_effect = error
        
        result = await tool_executor.execute_tool("customer_getCustomer", {"customer_id": "cust-999"})
        
        assert result["isError"] is True
        assert "HTTP error: 404" in result["content"][0]["text"]
        assert result["_meta"]["error_code"] == 404
    
    async def test_execute_tool_request_error(self, tool_executor, mock_http_client):
        """Test handling request errors"""
        # Mock request error
        mock_http_client.get.side_effect = httpx.RequestError("Connection failed")
        
        result = await tool_executor.execute_tool("customer_getCustomer", {"customer_id": "cust-001"})
        
        assert result["isError"] is True
        assert "Request error: Connection failed" in result["content"][0]["text"]
        assert result["_meta"]["error_code"] == 503
    
    async def test_execute_tool_unexpected_error(self, tool_executor, mock_tool_generator):
        """Test handling unexpected errors"""
        # Mock unexpected error
        mock_tool_generator.get_tool.side_effect = Exception("Unexpected error")
        
        result = await tool_executor.execute_tool("customer_getCustomer", {"customer_id": "cust-001"})
        
        assert result["isError"] is True
        assert "Internal error: Unexpected error" in result["content"][0]["text"]
        assert result["_meta"]["error_code"] == 500
    
    async def test_execute_http_request_get(self, tool_executor, mock_http_client):
        """Test HTTP GET request execution"""
        await tool_executor._execute_http_request("customer", "GET", "/customers/123", {})
        
        mock_http_client.get.assert_called_once_with("customer", "/customers/123")
    
    async def test_execute_http_request_post(self, tool_executor, mock_http_client):
        """Test HTTP POST request execution"""
        await tool_executor._execute_http_request("customer", "POST", "/customers", {"json": {"name": "John"}})
        
        mock_http_client.post.assert_called_once_with("customer", "/customers", json={"name": "John"})
    
    async def test_execute_http_request_put(self, tool_executor, mock_http_client):
        """Test HTTP PUT request execution"""
        await tool_executor._execute_http_request("customer", "PUT", "/customers/123", {"json": {"name": "John"}})
        
        mock_http_client.put.assert_called_once_with("customer", "/customers/123", json={"name": "John"})
    
    async def test_execute_http_request_delete(self, tool_executor, mock_http_client):
        """Test HTTP DELETE request execution"""
        await tool_executor._execute_http_request("customer", "DELETE", "/customers/123", {})
        
        mock_http_client.delete.assert_called_once_with("customer", "/customers/123")
    
    async def test_execute_http_request_patch(self, tool_executor, mock_http_client):
        """Test HTTP PATCH request execution"""
        await tool_executor._execute_http_request("customer", "PATCH", "/customers/123", {"json": {"name": "John"}})
        
        mock_http_client.patch.assert_called_once_with("customer", "/customers/123", json={"name": "John"})
    
    async def test_execute_http_request_unsupported_method(self, tool_executor):
        """Test unsupported HTTP method"""
        with pytest.raises(ValueError, match="Unsupported HTTP method: OPTIONS"):
            await tool_executor._execute_http_request("customer", "OPTIONS", "/customers", {})
    
    def test_validate_arguments_success(self, tool_executor, mock_tool_generator):
        """Test successful argument validation"""
        tool = mock_tool_generator.get_tool.return_value
        
        error = tool_executor._validate_arguments(tool, {"customer_id": "cust-001"})
        
        assert error is None
    
    def test_validate_arguments_missing_required(self, tool_executor, mock_tool_generator):
        """Test validation with missing required field"""
        tool = mock_tool_generator.get_tool.return_value
        
        error = tool_executor._validate_arguments(tool, {})
        
        assert error is not None
        assert "Missing required parameter: customer_id" in error
    
    def test_validate_arguments_invalid_type(self, tool_executor, mock_tool_generator):
        """Test validation with invalid type"""
        tool = mock_tool_generator.get_tool.return_value
        
        error = tool_executor._validate_arguments(tool, {
            "customer_id": "cust-001",
            "include_orders": "not_boolean"
        })
        
        assert error is not None
        assert "Invalid type for parameter 'include_orders'" in error
    
    def test_validate_type(self, tool_executor):
        """Test type validation"""
        assert tool_executor._validate_type("hello", "string") is True
        assert tool_executor._validate_type(123, "integer") is True
        assert tool_executor._validate_type(123.45, "number") is True
        assert tool_executor._validate_type(123, "number") is True  # int is also number
        assert tool_executor._validate_type(True, "boolean") is True
        assert tool_executor._validate_type([], "array") is True
        assert tool_executor._validate_type({}, "object") is True
        
        # Invalid types
        assert tool_executor._validate_type(123, "string") is False
        assert tool_executor._validate_type("hello", "integer") is False
        assert tool_executor._validate_type(True, "string") is False
        
        # Unknown type (should pass)
        assert tool_executor._validate_type("anything", "unknown_type") is True
    
    async def test_list_available_tools(self, tool_executor, mock_tool_generator):
        """Test listing available tools"""
        tools = await tool_executor.list_available_tools()
        
        assert len(tools) == 1
        assert tools[0]["name"] == "customer_getCustomer"
        assert tools[0]["description"] == "Get customer by ID"
        assert "inputSchema" in tools[0]
    
    async def test_get_tool_info(self, tool_executor, mock_tool_generator):
        """Test getting tool information"""
        info = await tool_executor.get_tool_info("customer_getCustomer")
        
        assert info is not None
        assert info["name"] == "customer_getCustomer"
        assert info["_meta"]["service"] == "customer"
        assert info["_meta"]["endpoint"] == "/customers/{customer_id}"
        assert info["_meta"]["method"] == "GET"
    
    async def test_get_tool_info_not_found(self, tool_executor, mock_tool_generator):
        """Test getting info for non-existent tool"""
        mock_tool_generator.get_tool.return_value = None
        
        info = await tool_executor.get_tool_info("nonexistent_tool")
        
        assert info is None
    
    async def test_health_check(self, tool_executor, mock_tool_generator):
        """Test health check"""
        # Mock service discovery
        mock_service_discovery = MagicMock()
        mock_service_discovery.get_healthy_services.return_value = {"customer", "order"}
        mock_tool_generator.service_discovery = mock_service_discovery
        
        health = await tool_executor.health_check()
        
        assert health["status"] == "healthy"
        assert health["tools_available"] == 1
        assert health["healthy_services"] == 2
        assert health["system"] == "tool_executor"