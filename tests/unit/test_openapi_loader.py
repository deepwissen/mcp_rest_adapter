import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import sys
import os

# Add the mcp_adapter directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from mcp_adapter.openapi_loader import OpenAPILoader, OpenAPISpec, OpenAPIEndpoint

@pytest.fixture
def openapi_loader():
    """Create OpenAPI loader instance"""
    return OpenAPILoader(refresh_interval=1)  # Short interval for testing

@pytest.fixture
def mock_http_client():
    """Mock HTTP client"""
    with patch('mcp_adapter.openapi_loader.http_client') as mock:
        yield mock

@pytest.fixture
def mock_service_discovery():
    """Mock service discovery"""
    with patch('mcp_adapter.openapi_loader.service_discovery') as mock:
        mock.get_healthy_services.return_value = {"test-service", "another-service"}
        yield mock

@pytest.fixture
def sample_openapi_spec():
    """Sample OpenAPI specification"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Test API",
            "version": "1.0.0",
            "description": "Test API description"
        },
        "paths": {
            "/users": {
                "get": {
                    "operationId": "listUsers",
                    "summary": "List users",
                    "description": "Get a list of users",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 10}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of users",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    },
                    "tags": ["users"]
                },
                "post": {
                    "operationId": "createUser",
                    "summary": "Create user",
                    "description": "Create a new user",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "User created"
                        }
                    },
                    "tags": ["users"]
                }
            },
            "/users/{id}": {
                "get": {
                    "operationId": "getUserById",
                    "summary": "Get user by ID",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "User details"
                        },
                        "404": {
                            "description": "User not found"
                        }
                    },
                    "tags": ["users"]
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "email": {"type": "string"}
                    }
                }
            }
        }
    }

@pytest.mark.asyncio
class TestOpenAPILoader:
    
    async def test_start_stop_loading(self, openapi_loader):
        """Test starting and stopping OpenAPI spec loading"""
        with patch.object(openapi_loader, 'load_all_specs') as mock_load:
            mock_load.return_value = None
            
            await openapi_loader.start_loading()
            mock_load.assert_called_once()
            
            assert openapi_loader._refresh_task is not None
            assert not openapi_loader._refresh_task.done()
            
            await openapi_loader.stop_loading()
            assert openapi_loader._refresh_task.done()
    
    async def test_load_spec_success(self, openapi_loader, mock_http_client, sample_openapi_spec):
        """Test successful OpenAPI spec loading"""
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_openapi_spec
        mock_http_client.get.return_value = mock_response
        
        spec = await openapi_loader.load_spec("test-service")
        
        assert spec is not None
        assert spec.service_name == "test-service"
        assert spec.title == "Test API"
        assert spec.version == "1.0.0"
        assert len(spec.endpoints) == 3  # GET /users, POST /users, GET /users/{id}
        
        # Check that spec was stored
        assert "test-service" in openapi_loader.specs
        assert openapi_loader.get_spec("test-service") == spec
    
    async def test_load_spec_failure(self, openapi_loader, mock_http_client):
        """Test failed OpenAPI spec loading"""
        mock_http_client.get.side_effect = Exception("Network error")
        
        spec = await openapi_loader.load_spec("test-service")
        
        assert spec is None
        assert "test-service" not in openapi_loader.specs
    
    async def test_load_all_specs(self, openapi_loader, mock_service_discovery, mock_http_client, sample_openapi_spec):
        """Test loading all specs for healthy services"""
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_openapi_spec
        mock_http_client.get.return_value = mock_response
        
        await openapi_loader.load_all_specs()
        
        # Should have called load_spec for each healthy service
        assert mock_http_client.get.call_count == 2
        mock_http_client.get.assert_any_call("test-service", "/openapi.json")
        mock_http_client.get.assert_any_call("another-service", "/openapi.json")
        
        # Both specs should be loaded
        assert len(openapi_loader.specs) == 2
        assert "test-service" in openapi_loader.specs
        assert "another-service" in openapi_loader.specs
    
    async def test_parse_openapi_spec(self, openapi_loader, sample_openapi_spec):
        """Test parsing OpenAPI specification"""
        spec = openapi_loader._parse_openapi_spec("test-service", sample_openapi_spec)
        
        assert spec is not None
        assert spec.service_name == "test-service"
        assert spec.title == "Test API"
        assert spec.version == "1.0.0"
        assert len(spec.endpoints) == 3
        
        # Check endpoints
        endpoints = {ep.operation_id: ep for ep in spec.endpoints}
        
        # GET /users
        list_users = endpoints["listUsers"]
        assert list_users.path == "/users"
        assert list_users.method == "GET"
        assert list_users.summary == "List users"
        assert len(list_users.parameters) == 1
        assert list_users.tags == ["users"]
        
        # POST /users
        create_user = endpoints["createUser"]
        assert create_user.path == "/users"
        assert create_user.method == "POST"
        assert create_user.summary == "Create user"
        assert create_user.request_body is not None
        
        # GET /users/{id}
        get_user = endpoints["getUserById"]
        assert get_user.path == "/users/{id}"
        assert get_user.method == "GET"
        assert len(get_user.parameters) == 1
        assert get_user.parameters[0]["name"] == "id"
    
    async def test_parse_operation(self, openapi_loader):
        """Test parsing individual operation"""
        operation = {
            "operationId": "testOperation",
            "summary": "Test operation",
            "description": "Test operation description",
            "parameters": [
                {
                    "name": "param1",
                    "in": "query",
                    "schema": {"type": "string"}
                }
            ],
            "responses": {
                "200": {"description": "Success"}
            },
            "tags": ["test"]
        }
        
        endpoint = openapi_loader._parse_operation("/test", "GET", operation)
        
        assert endpoint is not None
        assert endpoint.path == "/test"
        assert endpoint.method == "GET"
        assert endpoint.operation_id == "testOperation"
        assert endpoint.summary == "Test operation"
        assert endpoint.description == "Test operation description"
        assert len(endpoint.parameters) == 1
        assert endpoint.tags == ["test"]
    
    async def test_parse_operation_with_defaults(self, openapi_loader):
        """Test parsing operation with minimal information"""
        operation = {
            "responses": {
                "200": {"description": "Success"}
            }
        }
        
        endpoint = openapi_loader._parse_operation("/test", "POST", operation)
        
        assert endpoint is not None
        assert endpoint.path == "/test"
        assert endpoint.method == "POST"
        assert endpoint.operation_id == "post_test"  # Generated from method + path
        assert endpoint.summary == ""
        assert endpoint.description == ""
        assert len(endpoint.parameters) == 0
        assert endpoint.tags == []
    
    async def test_parse_operation_failure(self, openapi_loader):
        """Test parsing operation with invalid data"""
        # Missing responses
        operation = {
            "operationId": "testOperation"
        }
        
        endpoint = openapi_loader._parse_operation("/test", "GET", operation)
        
        # Should still create endpoint with empty responses
        assert endpoint is not None
        assert endpoint.responses == {}
    
    async def test_get_endpoints_by_service(self, openapi_loader, mock_http_client, sample_openapi_spec):
        """Test getting endpoints for a specific service"""
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_openapi_spec
        mock_http_client.get.return_value = mock_response
        
        await openapi_loader.load_spec("test-service")
        
        endpoints = openapi_loader.get_endpoints_by_service("test-service")
        assert len(endpoints) == 3
        
        # Test non-existent service
        endpoints = openapi_loader.get_endpoints_by_service("non-existent")
        assert len(endpoints) == 0
    
    async def test_get_all_specs(self, openapi_loader, mock_service_discovery, mock_http_client, sample_openapi_spec):
        """Test getting all loaded specs"""
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_openapi_spec
        mock_http_client.get.return_value = mock_response
        
        await openapi_loader.load_all_specs()
        
        all_specs = openapi_loader.get_all_specs()
        assert len(all_specs) == 2
        assert "test-service" in all_specs
        assert "another-service" in all_specs
        
        # Test that returned dict is a copy
        all_specs["fake-service"] = MagicMock()
        assert "fake-service" not in openapi_loader.get_all_specs()
    
    async def test_refresh_specs_loop(self, openapi_loader, mock_service_discovery, mock_http_client, sample_openapi_spec):
        """Test periodic refresh of specs"""
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_openapi_spec
        mock_http_client.get.return_value = mock_response
        
        # Mock asyncio.sleep to speed up test
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None
            
            await openapi_loader.start_loading()
            
            # Wait a bit for refresh loop to run
            await asyncio.sleep(0.1)
            
            await openapi_loader.stop_loading()
        
        # Should have called load_all_specs multiple times
        assert mock_http_client.get.call_count >= 2
    
    async def test_refresh_specs_exception_handling(self, openapi_loader, mock_service_discovery, mock_http_client):
        """Test refresh continues after exceptions"""
        mock_http_client.get.side_effect = Exception("Network error")
        
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None
            
            await openapi_loader.start_loading()
            
            # Wait a bit
            await asyncio.sleep(0.1)
            
            await openapi_loader.stop_loading()
        
        # Should have attempted to load specs despite exceptions
        assert mock_http_client.get.call_count >= 2
    
    async def test_invalid_openapi_spec(self, openapi_loader, mock_http_client):
        """Test handling of invalid OpenAPI spec"""
        invalid_spec = {
            "not_openapi": "invalid"
        }
        
        mock_response = AsyncMock()
        mock_response.json.return_value = invalid_spec
        mock_http_client.get.return_value = mock_response
        
        spec = await openapi_loader.load_spec("test-service")
        
        # Should handle gracefully and return spec with empty endpoints
        assert spec is not None
        assert len(spec.endpoints) == 0
    
    async def test_spec_timestamps(self, openapi_loader, mock_http_client, sample_openapi_spec):
        """Test that loaded_at timestamps are set correctly"""
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_openapi_spec
        mock_http_client.get.return_value = mock_response
        
        before_load = datetime.utcnow()
        spec = await openapi_loader.load_spec("test-service")
        after_load = datetime.utcnow()
        
        assert spec is not None
        assert before_load <= spec.loaded_at <= after_load
    
    async def test_openapi_endpoint_dataclass(self):
        """Test OpenAPIEndpoint dataclass"""
        endpoint = OpenAPIEndpoint(
            path="/test",
            method="GET",
            operation_id="testOp",
            summary="Test",
            description="Test endpoint",
            parameters=[],
            request_body=None,
            responses={},
            security=[],
            tags=["test"]
        )
        
        assert endpoint.path == "/test"
        assert endpoint.method == "GET"
        assert endpoint.operation_id == "testOp"
        assert endpoint.summary == "Test"
        assert endpoint.description == "Test endpoint"
        assert endpoint.parameters == []
        assert endpoint.request_body is None
        assert endpoint.responses == {}
        assert endpoint.security == []
        assert endpoint.tags == ["test"]
    
    async def test_openapi_spec_dataclass(self, sample_openapi_spec):
        """Test OpenAPISpec dataclass"""
        now = datetime.utcnow()
        spec = OpenAPISpec(
            service_name="test",
            title="Test API",
            version="1.0.0",
            base_path="/",
            endpoints=[],
            loaded_at=now,
            raw_spec=sample_openapi_spec
        )
        
        assert spec.service_name == "test"
        assert spec.title == "Test API"
        assert spec.version == "1.0.0"
        assert spec.base_path == "/"
        assert spec.endpoints == []
        assert spec.loaded_at == now
        assert spec.raw_spec == sample_openapi_spec
    
    async def test_custom_refresh_interval(self):
        """Test custom refresh interval"""
        custom_loader = OpenAPILoader(refresh_interval=10)
        assert custom_loader.refresh_interval == 10
        
        # Test with very short interval
        fast_loader = OpenAPILoader(refresh_interval=0.1)
        assert fast_loader.refresh_interval == 0.1