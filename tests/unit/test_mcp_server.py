import pytest
from fastapi.testclient import TestClient
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add the mcp_adapter directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from mcp_adapter.server import app, mcp_server, sessions, create_success_response, create_error_response

@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)

@pytest.fixture(autouse=True)
def reset_sessions():
    """Reset sessions before each test"""
    sessions.clear()
    yield
    sessions.clear()

class TestMCPServer:
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "mcp-adapter"}
    
    def test_initialize_request(self, client):
        """Test MCP initialize request"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        response = client.post("/mcp", json=request_data)
        assert response.status_code == 200
        
        # Check response structure
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "protocolVersion" in data["result"]
        assert "capabilities" in data["result"]
        assert "serverInfo" in data["result"]
        
        # Check session header
        assert "mcp-session-id" in response.headers
        session_id = response.headers["mcp-session-id"]
        assert session_id in sessions
    
    def test_initialize_with_existing_session(self, client):
        """Test initialize with existing session ID"""
        existing_session_id = "test-session-123"
        
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}}
            }
        }
        
        response = client.post(
            "/mcp",
            json=request_data,
            headers={"Mcp-Session-Id": existing_session_id}
        )
        
        assert response.status_code == 200
        assert response.headers["mcp-session-id"] == existing_session_id
    
    def test_invalid_jsonrpc_version(self, client):
        """Test request with invalid JSON-RPC version"""
        request_data = {
            "jsonrpc": "1.0",  # Invalid version
            "id": 1,
            "method": "initialize",
            "params": {}
        }
        
        response = client.post("/mcp", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32600
        assert "Invalid JSON-RPC version" in data["error"]["message"]
    
    def test_method_not_found(self, client):
        """Test calling non-existent method"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "non_existent_method",
            "params": {}
        }
        
        response = client.post("/mcp", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601
        assert "Method not found" in data["error"]["message"]
    
    def test_parse_error(self, client):
        """Test sending invalid JSON"""
        response = client.post(
            "/mcp",
            content="invalid json{",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32700
        assert "Parse error" in data["error"]["message"]
    
    def test_notifications_initialized(self, client):
        """Test initialized notification"""
        request_data = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        response = client.post("/mcp", json=request_data)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_tools_list_empty(self, client):
        """Test listing tools when none are registered"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = client.post("/mcp", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert "result" in data
        assert data["result"]["tools"] == []
    
    def test_tools_call_not_found(self, client):
        """Test calling a non-existent tool"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "non_existent_tool",
                "arguments": {}
            }
        }
        
        response = client.post("/mcp", json=request_data)
        assert response.status_code == 400
    
    def test_create_success_response(self):
        """Test success response creation"""
        response = create_success_response(123, {"data": "test"})
        assert response == {
            "jsonrpc": "2.0",
            "id": 123,
            "result": {"data": "test"}
        }
    
    def test_create_error_response(self):
        """Test error response creation"""
        response = create_error_response(456, -32600, "Test error")
        assert response == {
            "jsonrpc": "2.0",
            "id": 456,
            "error": {
                "code": -32600,
                "message": "Test error"
            }
        }
    
    def test_request_without_id(self, client):
        """Test notification-style request without ID"""
        request_data = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        response = client.post("/mcp", json=request_data)
        assert response.status_code == 200
    
    def test_internal_error_handling(self, client):
        """Test internal error handling"""
        # Mock the handle_initialize method to raise an exception
        with patch.object(mcp_server, 'handle_initialize', side_effect=Exception("Test error")):
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {}
            }
            
            response = client.post("/mcp", json=request_data)
            assert response.status_code == 200
            
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == -32603
            assert "Internal error" in data["error"]["message"]
    
    def test_concurrent_session_creation(self, client):
        """Test concurrent session creation doesn't cause issues"""
        import threading
        import time
        
        results = []
        
        def make_request():
            request_data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}}
                }
            }
            response = client.post("/mcp", json=request_data)
            results.append(response.headers.get("mcp-session-id"))
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All session IDs should be unique
        assert len(set(results)) == len(results)