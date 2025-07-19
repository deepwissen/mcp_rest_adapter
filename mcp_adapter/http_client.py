import httpx
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ServiceConfig:
    name: str
    base_url: str
    timeout: float = 30.0
    retries: int = 3
    auth_token: Optional[str] = None

class BackendHTTPClient:
    def __init__(self, service_configs: Dict[str, ServiceConfig]):
        self.service_configs = service_configs
        self.clients: Dict[str, httpx.AsyncClient] = {}
        
    async def initialize(self):
        """Initialize HTTP clients for each service"""
        for service_name, config in self.service_configs.items():
            headers = {"Content-Type": "application/json"}
            if config.auth_token:
                headers["Authorization"] = f"Bearer {config.auth_token}"
                
            client = httpx.AsyncClient(
                base_url=config.base_url,
                headers=headers,
                timeout=config.timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
            
            self.clients[service_name] = client
            logger.info(f"Initialized HTTP client for {service_name}")
    
    async def get(self, service_name: str, path: str, **kwargs) -> httpx.Response:
        """Make GET request to service"""
        return await self._request(service_name, "GET", path, **kwargs)
    
    async def post(self, service_name: str, path: str, **kwargs) -> httpx.Response:
        """Make POST request to service"""
        return await self._request(service_name, "POST", path, **kwargs)
    
    async def put(self, service_name: str, path: str, **kwargs) -> httpx.Response:
        """Make PUT request to service"""
        return await self._request(service_name, "PUT", path, **kwargs)
    
    async def delete(self, service_name: str, path: str, **kwargs) -> httpx.Response:
        """Make DELETE request to service"""
        return await self._request(service_name, "DELETE", path, **kwargs)
    
    async def patch(self, service_name: str, path: str, **kwargs) -> httpx.Response:
        """Make PATCH request to service"""
        return await self._request(service_name, "PATCH", path, **kwargs)
    
    async def _request(self, service_name: str, method: str, path: str, **kwargs) -> httpx.Response:
        """Make HTTP request with retry logic"""
        if service_name not in self.clients:
            raise ValueError(f"Service not configured: {service_name}")
        
        client = self.clients[service_name]
        config = self.service_configs[service_name]
        
        for attempt in range(config.retries + 1):
            try:
                logger.info(f"{method} {service_name}{path} (attempt {attempt + 1})")
                
                response = await client.request(method, path, **kwargs)
                
                # Log response details
                logger.info(f"Response: {response.status_code} from {service_name}{path}")
                
                # Raise for HTTP errors (4xx, 5xx)
                response.raise_for_status()
                
                return response
                
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} from {service_name}{path}")
                if e.response.status_code < 500 or attempt == config.retries:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except httpx.RequestError as e:
                logger.warning(f"Request error to {service_name}{path}: {e}")
                if attempt == config.retries:
                    raise
                await asyncio.sleep(2 ** attempt)
        
        raise Exception(f"Max retries exceeded for {service_name}{path}")
    
    async def health_check(self, service_name: str) -> bool:
        """Check if service is healthy"""
        try:
            response = await self.get(service_name, "/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {service_name}: {e}")
            return False
    
    async def close(self):
        """Close all HTTP clients"""
        for service_name, client in self.clients.items():
            await client.aclose()
            logger.info(f"Closed HTTP client for {service_name}")

# Configuration
SERVICE_CONFIGS = {
    "customer": ServiceConfig(
        name="customer",
        base_url="http://localhost:8001",
        timeout=30.0,
        retries=3
    ),
    "order": ServiceConfig(
        name="order", 
        base_url="http://localhost:8002",
        timeout=30.0,
        retries=3
    ),
    "inventory": ServiceConfig(
        name="inventory",
        base_url="http://localhost:8003", 
        timeout=30.0,
        retries=3
    )
}

# Global HTTP client instance
http_client = BackendHTTPClient(SERVICE_CONFIGS)