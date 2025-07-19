import pytest
from unittest.mock import MagicMock
import json
import sys
import os

# Add the mcp_adapter directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from mcp_adapter.request_translator import RequestTranslator
from mcp_adapter.tool_generator import MCPTool

@pytest.fixture
def request_translator():
    """Request translator instance"""
    return RequestTranslator()

@pytest.fixture
def get_tool():
    """Sample GET tool"""
    return MCPTool(
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

@pytest.fixture
def post_tool():
    """Sample POST tool"""
    return MCPTool(
        name="customer_createCustomer",
        description="Create customer",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"}
            },
            "required": ["name", "email"]
        },
        service_name="customer",
        endpoint_path="/customers",
        http_method="POST",
        parameters=[],
        request_body={
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "phone": {"type": "string"}
                        },
                        "required": ["name", "email"]
                    }
                }
            }
        }
    )

class TestRequestTranslator:
    
    def test_translate_mcp_to_http_get_with_path_params(self, request_translator, get_tool):
        """Test translating MCP request to HTTP GET with path parameters"""
        arguments = {"customer_id": "cust-001"}
        
        path, method, request_kwargs = request_translator.translate_mcp_to_http(get_tool, arguments)
        
        assert path == "/customers/cust-001"
        assert method == "GET"
        assert request_kwargs == {"params": {}}
    
    def test_translate_mcp_to_http_get_with_query_params(self, request_translator, get_tool):
        """Test translating MCP request to HTTP GET with query parameters"""
        arguments = {"customer_id": "cust-001", "include_orders": True}
        
        path, method, request_kwargs = request_translator.translate_mcp_to_http(get_tool, arguments)
        
        assert path == "/customers/cust-001"
        assert method == "GET"
        assert request_kwargs == {"params": {"include_orders": True}}
    
    def test_translate_mcp_to_http_post_with_body(self, request_translator, post_tool):
        """Test translating MCP request to HTTP POST with request body"""
        arguments = {"name": "John Doe", "email": "john@example.com", "phone": "+1234567890"}
        
        path, method, request_kwargs = request_translator.translate_mcp_to_http(post_tool, arguments)
        
        assert path == "/customers"
        assert method == "POST"
        assert request_kwargs == {"json": {"name": "John Doe", "email": "john@example.com", "phone": "+1234567890"}}
    
    def test_translate_mcp_to_http_missing_path_param(self, request_translator, get_tool):
        """Test error when missing required path parameter"""
        arguments = {}  # Missing customer_id
        
        with pytest.raises(ValueError, match="Missing required path parameter: customer_id"):
            request_translator.translate_mcp_to_http(get_tool, arguments)
    
    def test_translate_mcp_to_http_with_body_argument(self, request_translator, post_tool):
        """Test translating with explicit body argument"""
        arguments = {"body": {"name": "Jane Doe", "email": "jane@example.com"}}
        
        path, method, request_kwargs = request_translator.translate_mcp_to_http(post_tool, arguments)
        
        assert path == "/customers"
        assert method == "POST"
        assert request_kwargs == {"json": {"name": "Jane Doe", "email": "jane@example.com"}}
    
    def test_translate_http_to_mcp_json_response(self, request_translator, get_tool):
        """Test translating HTTP JSON response to MCP format"""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "cust-001", "name": "John Doe"}
        mock_response.status_code = 200
        
        result = request_translator.translate_http_to_mcp(mock_response, get_tool)
        
        assert result["isError"] is False
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        
        # Check that JSON is properly formatted
        content_text = result["content"][0]["text"]
        parsed_json = json.loads(content_text)
        assert parsed_json["id"] == "cust-001"
        assert parsed_json["name"] == "John Doe"
        
        # Check metadata
        assert result["_meta"]["status_code"] == 200
        assert result["_meta"]["tool_name"] == "customer_getCustomer"
        assert result["_meta"]["service"] == "customer"
    
    def test_translate_http_to_mcp_text_response(self, request_translator, get_tool):
        """Test translating HTTP text response to MCP format"""
        # Mock response that fails JSON parsing
        mock_response = MagicMock()
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.text = "Plain text response"
        mock_response.status_code = 200
        
        result = request_translator.translate_http_to_mcp(mock_response, get_tool)
        
        assert result["isError"] is False
        assert result["content"][0]["text"] == "Plain text response"
    
    def test_translate_http_to_mcp_error(self, request_translator, get_tool):
        """Test error handling in HTTP to MCP translation"""
        # Mock response that raises exception
        mock_response = MagicMock()
        mock_response.json.side_effect = Exception("Parse error")
        mock_response.text = "Error response"
        
        # This should not raise an exception but return an error response
        result = request_translator.translate_http_to_mcp(mock_response, get_tool)
        
        assert result["isError"] is True
        assert "Error translating response" in result["content"][0]["text"]
    
    def test_build_path_simple(self, request_translator):
        """Test building path with single parameter"""
        path = request_translator._build_path("/customers/{id}", {"id": "123"})
        assert path == "/customers/123"
    
    def test_build_path_multiple_params(self, request_translator):
        """Test building path with multiple parameters"""
        path = request_translator._build_path("/customers/{customer_id}/orders/{order_id}", {
            "customer_id": "cust-001",
            "order_id": "ord-123"
        })
        assert path == "/customers/cust-001/orders/ord-123"
    
    def test_build_path_missing_param(self, request_translator):
        """Test building path with missing parameter"""
        with pytest.raises(ValueError, match="Missing required path parameter: id"):
            request_translator._build_path("/customers/{id}", {})
    
    def test_extract_query_params(self, request_translator):
        """Test extracting query parameters"""
        parameters = [
            {"name": "limit", "in": "query", "schema": {"type": "integer"}},
            {"name": "status", "in": "query", "schema": {"type": "string"}},
            {"name": "id", "in": "path", "schema": {"type": "string"}}  # Should be ignored
        ]
        
        arguments = {"limit": 10, "status": "active", "id": "123", "other": "value"}
        
        query_params = request_translator._extract_query_params(parameters, arguments)
        
        assert query_params == {"limit": 10, "status": "active"}
    
    def test_extract_query_params_missing_optional(self, request_translator):
        """Test extracting query parameters with missing optional parameter"""
        parameters = [
            {"name": "limit", "in": "query", "schema": {"type": "integer"}},
            {"name": "status", "in": "query", "schema": {"type": "string"}}
        ]
        
        arguments = {"limit": 10}  # Missing status
        
        query_params = request_translator._extract_query_params(parameters, arguments)
        
        assert query_params == {"limit": 10}
    
    def test_extract_request_body_with_body_arg(self, request_translator, post_tool):
        """Test extracting request body with explicit body argument"""
        arguments = {"body": {"name": "John", "email": "john@example.com"}}
        
        body = request_translator._extract_request_body(post_tool, arguments)
        
        assert body == {"name": "John", "email": "john@example.com"}
    
    def test_extract_request_body_from_args(self, request_translator, post_tool):
        """Test extracting request body from arguments"""
        arguments = {"name": "John", "email": "john@example.com", "phone": "+1234567890"}
        
        body = request_translator._extract_request_body(post_tool, arguments)
        
        assert body == {"name": "John", "email": "john@example.com", "phone": "+1234567890"}
    
    def test_extract_request_body_exclude_path_query_params(self, request_translator):
        """Test extracting request body excludes path and query parameters"""
        # Create a tool with mixed parameter types
        tool = MCPTool(
            name="test_tool",
            description="Test tool",
            input_schema={"type": "object"},
            service_name="test",
            endpoint_path="/customers/{customer_id}",
            http_method="POST",
            parameters=[
                {"name": "customer_id", "in": "path", "required": True, "schema": {"type": "string"}},
                {"name": "include_orders", "in": "query", "required": False, "schema": {"type": "boolean"}}
            ],
            request_body={"content": {"application/json": {"schema": {"type": "object"}}}}
        )
        
        arguments = {
            "customer_id": "cust-001",
            "include_orders": True,
            "name": "John",
            "email": "john@example.com"
        }
        
        body = request_translator._extract_request_body(tool, arguments)
        
        # Should only include body parameters
        assert body == {"name": "John", "email": "john@example.com"}
    
    def test_extract_request_body_no_body(self, request_translator, get_tool):
        """Test extracting request body when tool has no request body"""
        arguments = {"customer_id": "cust-001", "include_orders": True}
        
        body = request_translator._extract_request_body(get_tool, arguments)
        
        assert body is None
    
    def test_extract_request_body_empty_body(self, request_translator, post_tool):
        """Test extracting request body with no body arguments"""
        arguments = {}  # No body arguments
        
        body = request_translator._extract_request_body(post_tool, arguments)
        
        assert body == {}
    
    def test_create_error_response(self, request_translator):
        """Test creating error response"""
        error_response = request_translator.create_error_response("Test error", 400)
        
        assert error_response["isError"] is True
        assert error_response["content"][0]["type"] == "text"
        assert error_response["content"][0]["text"] == "Error: Test error"
        assert error_response["_meta"]["error_code"] == 400
        assert error_response["_meta"]["error_message"] == "Test error"
    
    def test_create_error_response_no_code(self, request_translator):
        """Test creating error response without error code"""
        error_response = request_translator.create_error_response("Test error")
        
        assert error_response["isError"] is True
        assert error_response["_meta"]["error_code"] is None
        assert error_response["_meta"]["error_message"] == "Test error"