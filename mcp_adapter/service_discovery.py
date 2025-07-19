import asyncio
import logging
from typing import Dict, Set, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from .http_client import http_client

logger = logging.getLogger(__name__)

@dataclass 
class ServiceStatus:
    name: str
    is_healthy: bool
    last_check: datetime
    consecutive_failures: int = 0
    last_error: str = ""

class ServiceDiscovery:
    def __init__(self, check_interval: int = 30):
        self.service_statuses: Dict[str, ServiceStatus] = {}
        self.check_interval = check_interval
        self.healthy_services: Set[str] = set()
        self._monitoring_task: Optional[asyncio.Task] = None
        
    async def start_monitoring(self):
        """Start background service monitoring"""
        # Run initial health check immediately
        await self._check_all_services()
        
        self._monitoring_task = asyncio.create_task(self._monitor_services())
        logger.info("Started service discovery monitoring")
        
    async def stop_monitoring(self):
        """Stop background monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped service discovery monitoring")
    
    async def _monitor_services(self):
        """Background task to monitor service health"""
        while True:
            try:
                await self._check_all_services()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in service monitoring: {e}")
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def _check_all_services(self):
        """Check health of all configured services"""
        tasks = []
        
        for service_name in http_client.service_configs.keys():
            task = asyncio.create_task(self._check_service_health(service_name))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_service_health(self, service_name: str):
        """Check health of a single service"""
        try:
            is_healthy = await http_client.health_check(service_name)
            
            if service_name not in self.service_statuses:
                self.service_statuses[service_name] = ServiceStatus(
                    name=service_name,
                    is_healthy=is_healthy,
                    last_check=datetime.utcnow()
                )
                # Add to healthy services if healthy on first check
                if is_healthy:
                    self.healthy_services.add(service_name)
                    logger.info(f"Service {service_name} is healthy on initial check")
            else:
                status = self.service_statuses[service_name]
                status.last_check = datetime.utcnow()
                
                if is_healthy:
                    if not status.is_healthy:
                        logger.info(f"Service {service_name} is now healthy")
                    status.is_healthy = True
                    status.consecutive_failures = 0
                    status.last_error = ""
                    self.healthy_services.add(service_name)
                else:
                    status.is_healthy = False
                    status.consecutive_failures += 1
                    self.healthy_services.discard(service_name)
                    if status.consecutive_failures == 1:
                        logger.warning(f"Service {service_name} became unhealthy")
                        
        except Exception as e:
            logger.error(f"Health check error for {service_name}: {e}")
            
            if service_name in self.service_statuses:
                status = self.service_statuses[service_name]
                status.is_healthy = False
                status.consecutive_failures += 1
                status.last_error = str(e)
                status.last_check = datetime.utcnow()
                self.healthy_services.discard(service_name)
    
    def is_service_healthy(self, service_name: str) -> bool:
        """Check if a service is currently healthy"""
        return service_name in self.healthy_services
    
    def get_healthy_services(self) -> Set[str]:
        """Get set of currently healthy services"""
        return self.healthy_services.copy()
    
    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        """Get detailed status for a service"""
        return self.service_statuses.get(service_name)
    
    def get_all_statuses(self) -> Dict[str, ServiceStatus]:
        """Get status for all services"""
        return self.service_statuses.copy()

# Global service discovery instance
service_discovery = ServiceDiscovery()