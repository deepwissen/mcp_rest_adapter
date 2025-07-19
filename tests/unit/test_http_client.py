import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the mcp_adapter directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from mcp_adapter.http_client import BackendHTTPClient, ServiceConfig

@pytest.fixture
def service_configs():
    """Create test service configurations"""
    return {
        "test-service": ServiceConfig(
            name="test-service",
            base_url="http://localhost:9000",
            timeout=5.0,
            retries=2,
            auth_token="test-token"
        ),
        "no-auth-service": ServiceConfig(
            name="no-auth-service",
            base_url="http://localhost:9001",
            timeout=3.0,
            retries=1
        )
    }

@pytest.fixture
async def http_client(service_configs):
    """Create HTTP client instance"""
    client = BackendHTTPClient(service_configs)
    await client.initialize()
    yield client
    await client.close()

@pytest.mark.asyncio
class TestHTTPClient:
    
    async def test_initialize(self, service_configs):
        """Test client initialization"""
        client = BackendHTTPClient(service_configs)
        assert len(client.clients) == 0
        
        await client.initialize()
        
        assert len(client.clients) == 2
        assert "test-service" in client.clients
        assert "no-auth-service" in client.clients
        
        # Check auth header is set correctly
        test_client = client.clients["test-service"]
        assert test_client.headers["Authorization"] == "Bearer test-token"
        
        # Check no auth header for service without token
        no_auth_client = client.clients["no-auth-service"]
        assert "Authorization" not in no_auth_client.headers
        
        await client.close()
    
    async def test_get_request(self, http_client):
        """Test GET request"""
        # Mock the httpx client
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(http_client.clients["test-service"], 'request', return_value=mock_response) as mock_request:
            response = await http_client.get("test-service", "/test")
            
            mock_request.assert_called_once_with("GET", "/test")
            assert response.status_code == 200
            assert response.json() == {"data": "test"}
    
    async def test_post_request(self, http_client):
        """Test POST request with data"""
        mock_response = AsyncMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(http_client.clients["test-service"], 'request', return_value=mock_response) as mock_request:
            response = await http_client.post("test-service", "/create", json={"name": "test"})
            
            mock_request.assert_called_once_with("POST", "/create", json={"name": "test"})
            assert response.status_code == 201
    
    async def test_put_request(self, http_client):
        """Test PUT request"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(http_client.clients["test-service"], 'request', return_value=mock_response) as mock_request:
            response = await http_client.put("test-service", "/update/123", json={"name": "updated"})
            
            mock_request.assert_called_once_with("PUT", "/update/123", json={"name": "updated"})
            assert response.status_code == 200
    
    async def test_delete_request(self, http_client):
        """Test DELETE request"""
        mock_response = AsyncMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(http_client.clients["test-service"], 'request', return_value=mock_response) as mock_request:
            response = await http_client.delete("test-service", "/delete/123")
            
            mock_request.assert_called_once_with("DELETE", "/delete/123")
            assert response.status_code == 204
    
    async def test_service_not_configured(self, http_client):
        """Test requesting non-configured service"""
        with pytest.raises(ValueError, match="Service not configured: unknown-service"):
            await http_client.get("unknown-service", "/test")
    
    async def test_retry_on_server_error(self, http_client):
        """Test retry logic on 5xx errors"""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )
        
        # Service is configured with 2 retries
        with patch.object(http_client.clients["test-service"], 'request', return_value=mock_response) as mock_request:
            with pytest.raises(httpx.HTTPStatusError):
                await http_client.get("test-service", "/test")
            
            # Should have tried 3 times (initial + 2 retries)
            assert mock_request.call_count == 3
    
    async def test_no_retry_on_client_error(self, http_client):
        """Test no retry on 4xx errors"""
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=mock_response
        )
        
        with patch.object(http_client.clients["test-service"], 'request', return_value=mock_response) as mock_request:
            with pytest.raises(httpx.HTTPStatusError):
                await http_client.get("test-service", "/test")
            
            # Should have tried only once (no retry on 4xx)
            assert mock_request.call_count == 1
    
    async def test_retry_on_request_error(self, http_client):
        """Test retry on connection errors"""
        with patch.object(http_client.clients["test-service"], 'request', 
                         side_effect=httpx.RequestError("Connection failed")) as mock_request:
            with pytest.raises(httpx.RequestError):
                await http_client.get("test-service", "/test")
            
            # Should have tried 3 times (initial + 2 retries)
            assert mock_request.call_count == 3
    
    async def test_health_check_success(self, http_client):
        """Test successful health check"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(http_client.clients["test-service"], 'request', return_value=mock_response):
            result = await http_client.health_check("test-service")
            assert result is True
    
    async def test_health_check_failure(self, http_client):
        """Test failed health check"""
        mock_response = AsyncMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service unavailable", request=MagicMock(), response=mock_response
        )
        
        with patch.object(http_client.clients["test-service"], 'request', return_value=mock_response):
            result = await http_client.health_check("test-service")
            assert result is False
    
    async def test_health_check_connection_error(self, http_client):
        """Test health check with connection error"""
        with patch.object(http_client.clients["test-service"], 'request', 
                         side_effect=httpx.RequestError("Connection failed")):
            result = await http_client.health_check("test-service")
            assert result is False
    
    async def test_close_clients(self, service_configs):
        """Test closing all HTTP clients"""
        client = BackendHTTPClient(service_configs)
        await client.initialize()
        
        # Mock the aclose method for each client
        for service_client in client.clients.values():
            service_client.aclose = AsyncMock()
        
        await client.close()
        
        # Verify all clients were closed
        for service_client in client.clients.values():
            service_client.aclose.assert_called_once()
    
    async def test_exponential_backoff(self, http_client):
        """Test exponential backoff timing"""
        import time
        
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )
        
        start_time = time.time()
        
        with patch.object(http_client.clients["test-service"], 'request', return_value=mock_response):
            with patch('asyncio.sleep') as mock_sleep:
                with pytest.raises(httpx.HTTPStatusError):
                    await http_client.get("test-service", "/test")
                
                # Check sleep was called with exponential backoff
                assert mock_sleep.call_count == 2  # 2 retries
                mock_sleep.assert_any_call(1)  # 2^0
                mock_sleep.assert_any_call(2)  # 2^1