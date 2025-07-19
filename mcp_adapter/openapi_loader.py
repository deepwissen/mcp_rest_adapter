import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from .http_client import http_client
from .service_discovery import service_discovery

logger = logging.getLogger(__name__)

@dataclass
class OpenAPIEndpoint:
    path: str
    method: str
    operation_id: str
    summary: str
    description: str
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    responses: Dict[str, Any]
    security: List[Dict[str, Any]]
    tags: List[str]

@dataclass
class OpenAPISpec:
    service_name: str
    title: str
    version: str
    base_path: str
    endpoints: List[OpenAPIEndpoint]
    loaded_at: datetime
    raw_spec: Dict[str, Any]

class OpenAPILoader:
    def __init__(self, refresh_interval: int = 300):  # 5 minutes
        self.specs: Dict[str, OpenAPISpec] = {}
        self.refresh_interval = refresh_interval
        self._refresh_task: Optional[asyncio.Task] = None
        
    async def start_loading(self):
        """Start background OpenAPI spec loading"""
        await self.load_all_specs()
        self._refresh_task = asyncio.create_task(self._refresh_specs())
        logger.info("Started OpenAPI spec loading")
        
    async def stop_loading(self):
        """Stop background loading"""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped OpenAPI spec loading")
    
    async def load_all_specs(self):
        """Load OpenAPI specs for all healthy services"""
        healthy_services = service_discovery.get_healthy_services()
        
        tasks = []
        for service_name in healthy_services:
            task = asyncio.create_task(self.load_spec(service_name))
            tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    service_name = list(healthy_services)[i]
                    logger.error(f"Failed to load spec for {service_name}: {result}")
    
    async def load_spec(self, service_name: str) -> Optional[OpenAPISpec]:
        """Load OpenAPI spec for a single service"""
        try:
            logger.info(f"Loading OpenAPI spec for {service_name}")
            
            response = await http_client.get(service_name, "/openapi.json")
            raw_spec = response.json()
            
            # Parse the OpenAPI specification
            spec = self._parse_openapi_spec(service_name, raw_spec)
            
            if spec:
                self.specs[service_name] = spec
                logger.info(f"Loaded {len(spec.endpoints)} endpoints for {service_name}")
                return spec
            
        except Exception as e:
            logger.error(f"Failed to load OpenAPI spec for {service_name}: {e}")
            
        return None
    
    def _parse_openapi_spec(self, service_name: str, raw_spec: Dict[str, Any]) -> Optional[OpenAPISpec]:
        """Parse raw OpenAPI spec into structured format"""
        try:
            info = raw_spec.get("info", {})
            paths = raw_spec.get("paths", {})
            
            endpoints = []
            
            for path, path_item in paths.items():
                for method, operation in path_item.items():
                    if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                        endpoint = self._parse_operation(path, method.upper(), operation)
                        if endpoint:
                            endpoints.append(endpoint)
            
            spec = OpenAPISpec(
                service_name=service_name,
                title=info.get("title", service_name),
                version=info.get("version", "1.0.0"),
                base_path="/",
                endpoints=endpoints,
                loaded_at=datetime.utcnow(),
                raw_spec=raw_spec
            )
            
            return spec
            
        except Exception as e:
            logger.error(f"Failed to parse OpenAPI spec for {service_name}: {e}")
            return None
    
    def _parse_operation(self, path: str, method: str, operation: Dict[str, Any]) -> Optional[OpenAPIEndpoint]:
        """Parse a single OpenAPI operation"""
        try:
            endpoint = OpenAPIEndpoint(
                path=path,
                method=method,
                operation_id=operation.get("operationId", f"{method.lower()}_{path.replace('/', '_')}"),
                summary=operation.get("summary", ""),
                description=operation.get("description", ""),
                parameters=operation.get("parameters", []),
                request_body=operation.get("requestBody"),
                responses=operation.get("responses", {}),
                security=operation.get("security", []),
                tags=operation.get("tags", [])
            )
            
            return endpoint
            
        except Exception as e:
            logger.error(f"Failed to parse operation {method} {path}: {e}")
            return None
    
    async def _refresh_specs(self):
        """Background task to refresh OpenAPI specs"""
        while True:
            try:
                await asyncio.sleep(self.refresh_interval)
                await self.load_all_specs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error refreshing OpenAPI specs: {e}")
    
    def get_spec(self, service_name: str) -> Optional[OpenAPISpec]:
        """Get OpenAPI spec for a service"""
        return self.specs.get(service_name)
    
    def get_all_specs(self) -> Dict[str, OpenAPISpec]:
        """Get all loaded OpenAPI specs"""
        return self.specs.copy()
    
    def get_endpoints_by_service(self, service_name: str) -> List[OpenAPIEndpoint]:
        """Get all endpoints for a service"""
        spec = self.specs.get(service_name)
        return spec.endpoints if spec else []

# Global OpenAPI loader instance
openapi_loader = OpenAPILoader()