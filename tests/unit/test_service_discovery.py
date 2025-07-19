import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import sys
import os

# Add the mcp_adapter directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from mcp_adapter.service_discovery import ServiceDiscovery, ServiceStatus

@pytest.fixture
def service_discovery():
    """Create service discovery instance"""
    return ServiceDiscovery(check_interval=1)  # Short interval for testing

@pytest.fixture
def mock_http_client():
    """Mock HTTP client"""
    with patch('mcp_adapter.service_discovery.http_client') as mock:
        mock.service_configs = {
            "test-service": MagicMock(name="test-service"),
            "another-service": MagicMock(name="another-service")
        }
        yield mock

@pytest.mark.asyncio
class TestServiceDiscovery:
    
    async def test_start_stop_monitoring(self, service_discovery):
        """Test starting and stopping monitoring"""
        assert service_discovery._monitoring_task is None
        
        await service_discovery.start_monitoring()
        assert service_discovery._monitoring_task is not None
        assert not service_discovery._monitoring_task.done()
        
        await service_discovery.stop_monitoring()
        assert service_discovery._monitoring_task.done()
    
    async def test_check_service_health_success(self, service_discovery, mock_http_client):
        """Test successful health check"""
        mock_http_client.health_check.return_value = True
        
        await service_discovery._check_service_health("test-service")
        
        # Check service was marked as healthy
        assert service_discovery.is_service_healthy("test-service")
        assert "test-service" in service_discovery.get_healthy_services()
        
        # Check service status was recorded
        status = service_discovery.get_service_status("test-service")
        assert status is not None
        assert status.is_healthy is True
        assert status.consecutive_failures == 0
    
    async def test_check_service_health_failure(self, service_discovery, mock_http_client):
        """Test failed health check"""
        mock_http_client.health_check.return_value = False
        
        await service_discovery._check_service_health("test-service")
        
        # Check service was marked as unhealthy
        assert not service_discovery.is_service_healthy("test-service")
        assert "test-service" not in service_discovery.get_healthy_services()
        
        # Check service status was recorded
        status = service_discovery.get_service_status("test-service")
        assert status is not None
        assert status.is_healthy is False
        assert status.consecutive_failures == 1
    
    async def test_check_service_health_exception(self, service_discovery, mock_http_client):
        """Test health check with exception"""
        mock_http_client.health_check.side_effect = Exception("Connection error")
        
        await service_discovery._check_service_health("test-service")
        
        # Check service was marked as unhealthy
        assert not service_discovery.is_service_healthy("test-service")
        
        # Check error was recorded
        status = service_discovery.get_service_status("test-service")
        assert status is not None
        assert status.is_healthy is False
        assert status.consecutive_failures == 1
        assert "Connection error" in status.last_error
    
    async def test_service_recovery(self, service_discovery, mock_http_client):
        """Test service recovery after failure"""
        # First fail the service
        mock_http_client.health_check.return_value = False
        await service_discovery._check_service_health("test-service")
        
        assert not service_discovery.is_service_healthy("test-service")
        status = service_discovery.get_service_status("test-service")
        assert status.consecutive_failures == 1
        
        # Now recover the service
        mock_http_client.health_check.return_value = True
        await service_discovery._check_service_health("test-service")
        
        assert service_discovery.is_service_healthy("test-service")
        status = service_discovery.get_service_status("test-service")
        assert status.consecutive_failures == 0
        assert status.last_error == ""
    
    async def test_consecutive_failures(self, service_discovery, mock_http_client):
        """Test consecutive failure counting"""
        mock_http_client.health_check.return_value = False
        
        # Simulate multiple consecutive failures
        for i in range(3):
            await service_discovery._check_service_health("test-service")
            status = service_discovery.get_service_status("test-service")
            assert status.consecutive_failures == i + 1
    
    async def test_check_all_services(self, service_discovery, mock_http_client):
        """Test checking all configured services"""
        mock_http_client.health_check.return_value = True
        
        await service_discovery._check_all_services()
        
        # Both services should be checked
        assert mock_http_client.health_check.call_count == 2
        mock_http_client.health_check.assert_any_call("test-service")
        mock_http_client.health_check.assert_any_call("another-service")
        
        # Both should be healthy
        assert service_discovery.is_service_healthy("test-service")
        assert service_discovery.is_service_healthy("another-service")
    
    async def test_get_healthy_services(self, service_discovery, mock_http_client):
        """Test getting set of healthy services"""
        # Mark one service as healthy, one as unhealthy
        mock_http_client.health_check.side_effect = [True, False]
        
        await service_discovery._check_all_services()
        
        healthy_services = service_discovery.get_healthy_services()
        assert len(healthy_services) == 1
        assert "test-service" in healthy_services
        assert "another-service" not in healthy_services
        
        # Test that returned set is a copy
        healthy_services.add("fake-service")
        assert "fake-service" not in service_discovery.get_healthy_services()
    
    async def test_get_all_statuses(self, service_discovery, mock_http_client):
        """Test getting all service statuses"""
        mock_http_client.health_check.return_value = True
        
        await service_discovery._check_all_services()
        
        all_statuses = service_discovery.get_all_statuses()
        assert len(all_statuses) == 2
        assert "test-service" in all_statuses
        assert "another-service" in all_statuses
        
        # Test that returned dict is a copy
        all_statuses["fake-service"] = ServiceStatus("fake", False, datetime.utcnow())
        assert "fake-service" not in service_discovery.get_all_statuses()
    
    async def test_monitoring_loop(self, service_discovery, mock_http_client):
        """Test monitoring loop execution"""
        mock_http_client.health_check.return_value = True
        
        # Start monitoring
        await service_discovery.start_monitoring()
        
        # Wait a bit for the monitoring loop to run
        await asyncio.sleep(0.1)
        
        # Stop monitoring
        await service_discovery.stop_monitoring()
        
        # Services should have been checked
        assert mock_http_client.health_check.call_count >= 2
    
    async def test_monitoring_exception_handling(self, service_discovery, mock_http_client):
        """Test monitoring continues after exceptions"""
        # First call succeeds, second raises exception
        mock_http_client.health_check.side_effect = [True, Exception("Network error")]
        
        # Mock asyncio.sleep to speed up test
        with patch('asyncio.sleep') as mock_sleep:
            mock_sleep.return_value = None
            
            await service_discovery.start_monitoring()
            
            # Wait a bit
            await asyncio.sleep(0.1)
            
            await service_discovery.stop_monitoring()
        
        # Health check should have been called despite exception
        assert mock_http_client.health_check.call_count >= 2
    
    async def test_service_status_dataclass(self):
        """Test ServiceStatus dataclass"""
        now = datetime.utcnow()
        status = ServiceStatus(
            name="test-service",
            is_healthy=True,
            last_check=now,
            consecutive_failures=0,
            last_error=""
        )
        
        assert status.name == "test-service"
        assert status.is_healthy is True
        assert status.last_check == now
        assert status.consecutive_failures == 0
        assert status.last_error == ""
    
    async def test_service_status_timestamps(self, service_discovery, mock_http_client):
        """Test that last_check timestamps are updated"""
        mock_http_client.health_check.return_value = True
        
        before_check = datetime.utcnow()
        await service_discovery._check_service_health("test-service")
        after_check = datetime.utcnow()
        
        status = service_discovery.get_service_status("test-service")
        assert before_check <= status.last_check <= after_check
    
    async def test_concurrent_health_checks(self, service_discovery, mock_http_client):
        """Test concurrent health checks don't interfere"""
        mock_http_client.health_check.return_value = True
        
        # Start multiple health checks concurrently
        tasks = []
        for _ in range(5):
            task = asyncio.create_task(service_discovery._check_service_health("test-service"))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # Service should still be healthy
        assert service_discovery.is_service_healthy("test-service")
        
        # Status should be consistent
        status = service_discovery.get_service_status("test-service")
        assert status.is_healthy is True
    
    async def test_custom_check_interval(self):
        """Test custom check interval"""
        custom_discovery = ServiceDiscovery(check_interval=5)
        assert custom_discovery.check_interval == 5
        
        # Test with very short interval
        fast_discovery = ServiceDiscovery(check_interval=0.1)
        assert fast_discovery.check_interval == 0.1