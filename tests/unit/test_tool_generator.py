import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the mcp_adapter directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from mcp_adapter.tool_generator import ToolGenerator, MCPTool
from mcp_adapter.openapi_loader import OpenAPIEndpoint, OpenAPISpec
from datetime import datetime

@pytest.fixture
def mock_openapi_loader():
    """Mock OpenAPI loader"""
    loader = MagicMock()
    return loader

@pytest.fixture
def mock_service_discovery():
    """Mock service discovery"""
    discovery = MagicMock()
    discovery.get_healthy_services.return_value = {"customer", "order"}
    return discovery

@pytest.fixture
def tool_generator(mock_openapi_loader, mock_service_discovery):
    """Create tool generator instance"""
    return ToolGenerator(mock_openapi_loader, mock_service_discovery)

@pytest.fixture
def sample_endpoint():
    """Sample OpenAPI endpoint"""
    return OpenAPIEndpoint(
        path="/customers/{customer_id}",
        method="GET",
        operation_id="getCustomer",
        summary="Get customer by ID",
        description="Retrieve a customer by their unique identifier",
        parameters=[
            {
                "name": "customer_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "Customer ID"
            },
            {
                "name": "include_orders",
                "in": "query",
                "required": False,
                "schema": {"type": "boolean", "default": False},
                "description": "Include customer orders"
            }
        ],
        request_body=None,
        responses={"200": {"description": "Customer details"}},
        security=[],
        tags=["customers"]
    )

@pytest.fixture
def sample_spec(sample_endpoint):
    """Sample OpenAPI spec"""
    return OpenAPISpec(
        service_name="customer",
        title="Customer API",
        version="1.0.0",
        base_path="/",
        endpoints=[sample_endpoint],
        loaded_at=datetime.utcnow(),
        raw_spec={}
    )

class TestToolGenerator:
    
    def test_generate_tool_from_endpoint(self, tool_generator, sample_endpoint):
        """Test generating a tool from an OpenAPI endpoint"""
        tool = tool_generator.generate_tool_from_endpoint("customer", sample_endpoint)
        
        assert tool is not None
        assert tool.name == "customer_getCustomer"
        assert tool.description == "Get customer by ID. Retrieve a customer by their unique identifier. Path parameters: customer_id"
        assert tool.service_name == "customer"
        assert tool.endpoint_path == "/customers/{customer_id}"
        assert tool.http_method == "GET"
        
        # Check input schema
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert "customer_id" in schema["properties"]
        assert "include_orders" in schema["properties"]
        assert "customer_id" in schema["required"]
        assert "include_orders" not in schema["required"]
    
    def test_generate_tool_name_from_operation_id(self, tool_generator, sample_endpoint):
        """Test tool name generation from operation ID"""
        tool_name = tool_generator._generate_tool_name("customer", sample_endpoint)
        assert tool_name == "customer_getCustomer"
    
    def test_generate_tool_name_fallback(self, tool_generator):
        """Test tool name generation fallback"""
        endpoint = OpenAPIEndpoint(
            path="/customers",
            method="GET",
            operation_id="",  # No operation ID
            summary="List customers",
            description="",
            parameters=[],
            request_body=None,
            responses={},
            security=[],
            tags=[]
        )
        
        tool_name = tool_generator._generate_tool_name("customer", endpoint)
        assert tool_name == "customer_get_customers"
    
    def test_generate_description_with_summary_and_description(self, tool_generator):
        """Test description generation with both summary and description"""
        endpoint = OpenAPIEndpoint(
            path="/customers/{id}",
            method="GET",
            operation_id="getCustomer",
            summary="Get customer",
            description="Retrieve customer details",
            parameters=[
                {
                    "name": "id",
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
        
        description = tool_generator._generate_description(endpoint)
        assert description == "Get customer. Retrieve customer details. Path parameters: id"
    
    def test_generate_description_fallback(self, tool_generator):
        """Test description generation fallback"""
        endpoint = OpenAPIEndpoint(
            path="/customers",
            method="POST",
            operation_id="",
            summary="",
            description="",
            parameters=[],
            request_body=None,
            responses={},
            security=[],
            tags=[]
        )
        
        description = tool_generator._generate_description(endpoint)
        assert description == "POST /customers"
    
    def test_generate_input_schema_with_request_body(self, tool_generator):
        """Test input schema generation with request body"""
        endpoint = OpenAPIEndpoint(
            path="/customers",
            method="POST",
            operation_id="createCustomer",
            summary="Create customer",
            description="",
            parameters=[],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"}
                            },
                            "required": ["name", "email"]
                        }
                    }
                }
            },
            responses={},
            security=[],
            tags=[]
        )
        
        schema = tool_generator._generate_input_schema(endpoint)
        
        assert "name" in schema["properties"]
        assert "email" in schema["properties"]
        assert "name" in schema["required"]
        assert "email" in schema["required"]
    
    def test_generate_input_schema_with_single_body(self, tool_generator):
        """Test input schema generation with single value request body"""
        endpoint = OpenAPIEndpoint(
            path="/customers",
            method="POST",
            operation_id="createCustomer",
            summary="Create customer",
            description="",
            parameters=[],
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "string"
                        }
                    }
                }
            },
            responses={},
            security=[],
            tags=[]
        )
        
        schema = tool_generator._generate_input_schema(endpoint)
        
        assert "body" in schema["properties"]
        assert schema["properties"]["body"]["type"] == "string"
        assert "body" in schema["required"]
    
    def test_generate_tools_for_service(self, tool_generator, sample_spec):
        """Test generating all tools for a service"""
        tools = tool_generator.generate_tools_for_service("customer", sample_spec)
        
        assert len(tools) == 1
        assert "customer_getCustomer" in tools
        
        tool = tools["customer_getCustomer"]
        assert tool.service_name == "customer"
        assert tool.endpoint_path == "/customers/{customer_id}"
    
    def test_generate_all_tools(self, tool_generator, mock_openapi_loader, sample_spec):
        """Test generating all tools from all services"""
        mock_openapi_loader.get_spec.return_value = sample_spec
        
        tools = tool_generator.generate_all_tools()
        
        # Should call get_spec for each healthy service
        assert mock_openapi_loader.get_spec.call_count == 2
        mock_openapi_loader.get_spec.assert_any_call("customer")
        mock_openapi_loader.get_spec.assert_any_call("order")
        
        # Should generate tools for each service
        assert len(tools) == 2  # One tool per service
    
    def test_generate_all_tools_missing_spec(self, tool_generator, mock_openapi_loader):
        """Test generating tools when spec is missing"""
        mock_openapi_loader.get_spec.return_value = None
        
        tools = tool_generator.generate_all_tools()
        
        assert len(tools) == 0
    
    def test_get_tool_o1_lookup(self, tool_generator, sample_spec):
        """Test O(1) tool lookup"""
        # First generate tools
        tool_generator.tools = {"test_tool": MCPTool(
            name="test_tool",
            description="Test tool",
            input_schema={"type": "object"},
            service_name="test",
            endpoint_path="/test",
            http_method="GET",
            parameters=[]
        )}
        
        # Test successful lookup
        tool = tool_generator.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"
        
        # Test failed lookup
        tool = tool_generator.get_tool("nonexistent_tool")
        assert tool is None
    
    def test_get_tools_for_service(self, tool_generator):
        """Test getting tools for specific service"""
        # Set up tools for different services
        tool_generator.tools = {
            "customer_tool": MCPTool(
                name="customer_tool",
                description="Customer tool",
                input_schema={"type": "object"},
                service_name="customer",
                endpoint_path="/customers",
                http_method="GET",
                parameters=[]
            ),
            "order_tool": MCPTool(
                name="order_tool",
                description="Order tool",
                input_schema={"type": "object"},
                service_name="order",
                endpoint_path="/orders",
                http_method="GET",
                parameters=[]
            )
        }
        
        # Test getting tools for specific service
        customer_tools = tool_generator.get_tools_for_service("customer")
        assert len(customer_tools) == 1
        assert "customer_tool" in customer_tools
        
        order_tools = tool_generator.get_tools_for_service("order")
        assert len(order_tools) == 1
        assert "order_tool" in order_tools
        
        # Test getting tools for nonexistent service
        nonexistent_tools = tool_generator.get_tools_for_service("nonexistent")
        assert len(nonexistent_tools) == 0
    
    def test_refresh_tools(self, tool_generator, mock_openapi_loader, sample_spec):
        """Test refreshing tools"""
        mock_openapi_loader.get_spec.return_value = sample_spec
        
        # Initial state
        assert len(tool_generator.tools) == 0
        
        # Refresh tools
        tool_generator.refresh_tools()
        
        # Should have generated tools
        assert len(tool_generator.tools) > 0
    
    def test_mcp_tool_to_dict(self):
        """Test MCPTool to_dict conversion"""
        tool = MCPTool(
            name="test_tool",
            description="Test tool description",
            input_schema={"type": "object", "properties": {"id": {"type": "string"}}},
            service_name="test",
            endpoint_path="/test",
            http_method="GET",
            parameters=[]
        )
        
        tool_dict = tool.to_dict()
        
        assert tool_dict["name"] == "test_tool"
        assert tool_dict["description"] == "Test tool description"
        assert tool_dict["inputSchema"]["type"] == "object"
        assert "properties" in tool_dict["inputSchema"]
    
    def test_generate_tool_error_handling(self, tool_generator):
        """Test error handling in tool generation"""
        # Create an endpoint that might cause errors
        bad_endpoint = OpenAPIEndpoint(
            path="/bad",
            method="GET",
            operation_id=None,
            summary=None,
            description=None,
            parameters=[
                {
                    "name": "bad_param",
                    "in": "invalid_location",  # Invalid parameter location
                    "schema": {"type": "string"}
                }
            ],
            request_body=None,
            responses={},
            security=[],
            tags=[]
        )
        
        # Should handle error gracefully
        tool = tool_generator.generate_tool_from_endpoint("test", bad_endpoint)
        # Should still generate a tool, just with empty schema
        assert tool is not None
        assert tool.name == "test_get_bad"