import logging
import asyncio
from typing import Dict, Any, Optional, List
import httpx
from .tool_generator import MCPTool, ToolGenerator
from .request_translator import RequestTranslator
from .http_client import BackendHTTPClient

logger = logging.getLogger(__name__)

class ToolExecutor:
    """Execute MCP tools by calling backend services"""
    
    def __init__(self, tool_generator: ToolGenerator, http_client: BackendHTTPClient, request_translator: RequestTranslator):
        self.tool_generator = tool_generator
        self.http_client = http_client
        self.request_translator = request_translator
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name with given arguments
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            MCP response dictionary
        """
        try:
            # Get tool definition (O(1) lookup)
            tool = self.tool_generator.get_tool(tool_name)
            if not tool:
                return self.request_translator.create_error_response(
                    f"Tool not found: {tool_name}", 
                    error_code=404
                )
            
            logger.info(f"Executing tool: {tool_name} with arguments: {arguments}")
            
            # Validate arguments
            validation_error = self._validate_arguments(tool, arguments)
            if validation_error:
                return self.request_translator.create_error_response(
                    validation_error,
                    error_code=400
                )
            
            # Translate MCP request to HTTP request
            path, method, request_kwargs = self.request_translator.translate_mcp_to_http(tool, arguments)
            
            # Execute HTTP request
            response = await self._execute_http_request(
                tool.service_name,
                method,
                path,
                request_kwargs
            )
            
            # Translate HTTP response to MCP response
            mcp_response = self.request_translator.translate_http_to_mcp(response, tool)
            
            logger.info(f"Tool {tool_name} executed successfully")
            return mcp_response
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error executing tool {tool_name}: {e}")
            return self.request_translator.create_error_response(
                f"HTTP error: {e.response.status_code} - {e.response.text}",
                error_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error(f"Request error executing tool {tool_name}: {e}")
            return self.request_translator.create_error_response(
                f"Request error: {e}",
                error_code=503
            )
        except Exception as e:
            logger.error(f"Unexpected error executing tool {tool_name}: {e}")
            return self.request_translator.create_error_response(
                f"Internal error: {e}",
                error_code=500
            )
    
    async def _execute_http_request(self, service_name: str, method: str, path: str, request_kwargs: Dict[str, Any]) -> httpx.Response:
        """Execute HTTP request to backend service"""
        method = method.upper()
        
        if method == 'GET':
            return await self.http_client.get(service_name, path, **request_kwargs)
        elif method == 'POST':
            return await self.http_client.post(service_name, path, **request_kwargs)
        elif method == 'PUT':
            return await self.http_client.put(service_name, path, **request_kwargs)
        elif method == 'DELETE':
            return await self.http_client.delete(service_name, path, **request_kwargs)
        elif method == 'PATCH':
            return await self.http_client.patch(service_name, path, **request_kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
    
    def _validate_arguments(self, tool: MCPTool, arguments: Dict[str, Any]) -> Optional[str]:
        """
        Validate tool arguments against input schema
        
        Returns:
            Error message if validation fails, None if valid
        """
        try:
            schema = tool.input_schema
            required_fields = schema.get('required', [])
            properties = schema.get('properties', {})
            
            # Check required fields
            for field in required_fields:
                if field not in arguments:
                    return f"Missing required parameter: {field}"
            
            # Check field types (basic validation)
            for field, value in arguments.items():
                if field in properties:
                    expected_type = properties[field].get('type')
                    if not self._validate_type(value, expected_type):
                        return f"Invalid type for parameter '{field}': expected {expected_type}, got {type(value).__name__}"
            
            return None
            
        except Exception as e:
            logger.error(f"Validation error for tool {tool.name}: {e}")
            return f"Validation error: {e}"
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value type against expected type"""
        if expected_type == 'string':
            return isinstance(value, str)
        elif expected_type == 'integer':
            return isinstance(value, int)
        elif expected_type == 'number':
            return isinstance(value, (int, float))
        elif expected_type == 'boolean':
            return isinstance(value, bool)
        elif expected_type == 'array':
            return isinstance(value, list)
        elif expected_type == 'object':
            return isinstance(value, dict)
        else:
            # Unknown type, allow it
            return True
    
    async def list_available_tools(self) -> List[Dict[str, Any]]:
        """List all available tools in MCP format"""
        tools = self.tool_generator.get_all_tools()
        return [tool.to_dict() for tool in tools.values()]
    
    async def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific tool"""
        tool = self.tool_generator.get_tool(tool_name)
        if not tool:
            return None
        
        info = tool.to_dict()
        info['_meta'] = {
            'service': tool.service_name,
            'endpoint': tool.endpoint_path,
            'method': tool.http_method
        }
        return info
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of tool execution system"""
        tool_count = len(self.tool_generator.get_all_tools())
        healthy_services = len(self.tool_generator.service_discovery.get_healthy_services())
        
        return {
            "status": "healthy",
            "tools_available": tool_count,
            "healthy_services": healthy_services,
            "system": "tool_executor"
        }

# Global tool executor instance
tool_executor = None

def get_tool_executor(tool_generator: ToolGenerator, http_client: BackendHTTPClient, request_translator: RequestTranslator) -> ToolExecutor:
    """Get or create the global tool executor instance"""
    global tool_executor
    if tool_executor is None:
        tool_executor = ToolExecutor(tool_generator, http_client, request_translator)
    return tool_executor