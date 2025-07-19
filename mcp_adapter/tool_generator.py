import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .openapi_loader import OpenAPILoader, OpenAPIEndpoint, OpenAPISpec
from .service_discovery import ServiceDiscovery
import re
import json

logger = logging.getLogger(__name__)

@dataclass
class MCPTool:
    """MCP tool definition"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    service_name: str
    endpoint_path: str
    http_method: str
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool format"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }

class ToolGenerator:
    """Generate MCP tools from OpenAPI specifications"""
    
    def __init__(self, openapi_loader: OpenAPILoader, service_discovery: ServiceDiscovery):
        self.openapi_loader = openapi_loader
        self.service_discovery = service_discovery
        self.tools: Dict[str, MCPTool] = {}
        
    def generate_all_tools(self) -> Dict[str, MCPTool]:
        """Generate MCP tools from all available OpenAPI specs"""
        self.tools.clear()
        
        healthy_services = self.service_discovery.get_healthy_services()
        logger.info(f"Generating tools for {len(healthy_services)} healthy services")
        
        for service_name in healthy_services:
            spec = self.openapi_loader.get_spec(service_name)
            if spec:
                service_tools = self.generate_tools_for_service(service_name, spec)
                self.tools.update(service_tools)
                logger.info(f"Generated {len(service_tools)} tools for {service_name}")
            else:
                logger.warning(f"No OpenAPI spec found for service: {service_name}")
        
        logger.info(f"Total tools generated: {len(self.tools)}")
        return self.tools
    
    def generate_tools_for_service(self, service_name: str, spec: OpenAPISpec) -> Dict[str, MCPTool]:
        """Generate MCP tools for a specific service"""
        tools = {}
        
        for endpoint in spec.endpoints:
            tool = self.generate_tool_from_endpoint(service_name, endpoint)
            if tool:
                tools[tool.name] = tool
        
        return tools
    
    def generate_tool_from_endpoint(self, service_name: str, endpoint: OpenAPIEndpoint) -> Optional[MCPTool]:
        """Generate a single MCP tool from an OpenAPI endpoint"""
        try:
            # Generate tool name
            tool_name = self._generate_tool_name(service_name, endpoint)
            
            # Generate description
            description = self._generate_description(endpoint)
            
            # Generate input schema
            input_schema = self._generate_input_schema(endpoint)
            
            tool = MCPTool(
                name=tool_name,
                description=description,
                input_schema=input_schema,
                service_name=service_name,
                endpoint_path=endpoint.path,
                http_method=endpoint.method,
                parameters=endpoint.parameters,
                request_body=endpoint.request_body
            )
            
            return tool
            
        except Exception as e:
            logger.error(f"Failed to generate tool for {service_name} {endpoint.method} {endpoint.path}: {e}")
            return None
    
    def _generate_tool_name(self, service_name: str, endpoint: OpenAPIEndpoint) -> str:
        """Generate a unique tool name"""
        if endpoint.operation_id:
            # Use operation ID if available
            base_name = endpoint.operation_id
        else:
            # Generate from method and path
            path_parts = [part for part in endpoint.path.split('/') if part and not part.startswith('{')]
            if path_parts:
                base_name = f"{endpoint.method.lower()}_{path_parts[-1]}"
            else:
                base_name = f"{endpoint.method.lower()}_root"
        
        # Add service prefix to avoid conflicts
        tool_name = f"{service_name}_{base_name}"
        
        # Ensure valid identifier
        tool_name = re.sub(r'[^a-zA-Z0-9_]', '_', tool_name)
        
        return tool_name
    
    def _generate_description(self, endpoint: OpenAPIEndpoint) -> str:
        """Generate tool description from endpoint metadata"""
        description_parts = []
        
        if endpoint.summary:
            description_parts.append(endpoint.summary)
        
        if endpoint.description and endpoint.description != endpoint.summary:
            description_parts.append(endpoint.description)
        
        if not description_parts:
            # Fallback description
            description_parts.append(f"{endpoint.method} {endpoint.path}")
        
        # Add path parameters info
        path_params = [p for p in endpoint.parameters if p.get('in') == 'path']
        if path_params:
            param_names = [p['name'] for p in path_params]
            description_parts.append(f"Path parameters: {', '.join(param_names)}")
        
        return '. '.join(description_parts)
    
    def _generate_input_schema(self, endpoint: OpenAPIEndpoint) -> Dict[str, Any]:
        """Generate JSON schema for tool input"""
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Add path parameters
        for param in endpoint.parameters:
            if param.get('in') == 'path':
                param_name = param['name']
                param_schema = param.get('schema', {'type': 'string'})
                
                schema['properties'][param_name] = {
                    "type": param_schema.get('type', 'string'),
                    "description": param.get('description', f"Path parameter: {param_name}")
                }
                
                if param.get('required', False):
                    schema['required'].append(param_name)
        
        # Add query parameters
        for param in endpoint.parameters:
            if param.get('in') == 'query':
                param_name = param['name']
                param_schema = param.get('schema', {'type': 'string'})
                
                prop_schema = {
                    "type": param_schema.get('type', 'string'),
                    "description": param.get('description', f"Query parameter: {param_name}")
                }
                
                # Add default value if present
                if 'default' in param_schema:
                    prop_schema['default'] = param_schema['default']
                
                # Add enum values if present
                if 'enum' in param_schema:
                    prop_schema['enum'] = param_schema['enum']
                
                schema['properties'][param_name] = prop_schema
                
                if param.get('required', False):
                    schema['required'].append(param_name)
        
        # Add request body parameters
        if endpoint.request_body:
            content = endpoint.request_body.get('content', {})
            json_content = content.get('application/json', {})
            body_schema = json_content.get('schema', {})
            
            if body_schema.get('type') == 'object':
                # Merge object properties
                properties = body_schema.get('properties', {})
                for prop_name, prop_schema in properties.items():
                    schema['properties'][prop_name] = {
                        "type": prop_schema.get('type', 'string'),
                        "description": prop_schema.get('description', f"Request body parameter: {prop_name}")
                    }
                
                # Add required fields
                required_fields = body_schema.get('required', [])
                for field in required_fields:
                    if field not in schema['required']:
                        schema['required'].append(field)
            else:
                # Single value request body
                schema['properties']['body'] = {
                    "type": body_schema.get('type', 'object'),
                    "description": "Request body data"
                }
                schema['required'].append('body')
        
        return schema
    
    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """Get a tool by name (O(1) lookup)"""
        return self.tools.get(tool_name)
    
    def get_all_tools(self) -> Dict[str, MCPTool]:
        """Get all tools"""
        return self.tools.copy()
    
    def get_tools_for_service(self, service_name: str) -> Dict[str, MCPTool]:
        """Get all tools for a specific service"""
        return {
            name: tool for name, tool in self.tools.items()
            if tool.service_name == service_name
        }
    
    def refresh_tools(self):
        """Refresh tools from current OpenAPI specs"""
        logger.info("Refreshing tools from OpenAPI specs")
        old_count = len(self.tools)
        self.generate_all_tools()
        new_count = len(self.tools)
        logger.info(f"Tool refresh complete: {old_count} → {new_count} tools")

# Global tool generator instance
tool_generator = None

def get_tool_generator(openapi_loader: OpenAPILoader, service_discovery: ServiceDiscovery) -> ToolGenerator:
    """Get or create the global tool generator instance"""
    global tool_generator
    if tool_generator is None:
        tool_generator = ToolGenerator(openapi_loader, service_discovery)
    return tool_generator