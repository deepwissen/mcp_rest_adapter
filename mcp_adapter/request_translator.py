import logging
from typing import Dict, Any, Optional, List, Tuple
import json
import re
from urllib.parse import urlencode
from .tool_generator import MCPTool

logger = logging.getLogger(__name__)

class RequestTranslator:
    """Translate MCP requests to HTTP requests and vice versa"""
    
    def __init__(self):
        pass
    
    def translate_mcp_to_http(self, tool: MCPTool, arguments: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        """
        Translate MCP tool call to HTTP request parameters
        
        Returns:
            Tuple of (path, method, request_kwargs)
        """
        try:
            # Extract path parameters
            path = self._build_path(tool.endpoint_path, arguments)
            
            # Extract query parameters
            query_params = self._extract_query_params(tool.parameters, arguments)
            
            # Extract request body
            request_body = self._extract_request_body(tool, arguments)
            
            # Build request kwargs
            request_kwargs = {}
            
            if query_params:
                request_kwargs['params'] = query_params
            
            if request_body is not None:
                request_kwargs['json'] = request_body
            
            logger.debug(f"Translated MCP call to: {tool.http_method} {path} with {request_kwargs}")
            
            return path, tool.http_method, request_kwargs
            
        except Exception as e:
            logger.error(f"Failed to translate MCP request: {e}")
            raise ValueError(f"Request translation failed: {e}")
    
    def translate_http_to_mcp(self, response, tool: MCPTool) -> Dict[str, Any]:
        """
        Translate HTTP response to MCP response format
        
        Args:
            response: HTTP response object
            tool: The tool that was called
            
        Returns:
            MCP response dictionary
        """
        try:
            # Get response content
            if hasattr(response, 'json'):
                try:
                    content = response.json()
                    content_text = json.dumps(content, indent=2)
                except:
                    content_text = response.text
            else:
                content_text = str(response)
            
            # Format as MCP response
            mcp_response = {
                "content": [
                    {
                        "type": "text",
                        "text": content_text
                    }
                ],
                "isError": False
            }
            
            # Add metadata
            if hasattr(response, 'status_code'):
                mcp_response["_meta"] = {
                    "status_code": response.status_code,
                    "tool_name": tool.name,
                    "service": tool.service_name
                }
            
            return mcp_response
            
        except Exception as e:
            logger.error(f"Failed to translate HTTP response: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error translating response: {e}"
                    }
                ],
                "isError": True
            }
    
    def _build_path(self, endpoint_path: str, arguments: Dict[str, Any]) -> str:
        """Build the actual path by replacing path parameters"""
        path = endpoint_path
        
        # Find all path parameters (e.g., {id}, {customer_id})
        path_params = re.findall(r'\{([^}]+)\}', path)
        
        for param in path_params:
            if param in arguments:
                # Replace {param} with actual value
                path = path.replace(f"{{{param}}}", str(arguments[param]))
            else:
                raise ValueError(f"Missing required path parameter: {param}")
        
        return path
    
    def _extract_query_params(self, parameters: List[Dict[str, Any]], arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Extract query parameters from arguments"""
        query_params = {}
        
        for param in parameters:
            if param.get('in') == 'query':
                param_name = param['name']
                if param_name in arguments:
                    query_params[param_name] = arguments[param_name]
        
        return query_params
    
    def _extract_request_body(self, tool: MCPTool, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract request body from arguments"""
        if not tool.request_body:
            return None
        
        # If there's a 'body' argument, use it directly
        if 'body' in arguments:
            return arguments['body']
        
        # Otherwise, build body from non-path/query parameters
        body = {}
        
        # Get all path and query parameter names
        path_params = set(re.findall(r'\{([^}]+)\}', tool.endpoint_path))
        query_params = set(param['name'] for param in tool.parameters if param.get('in') == 'query')
        excluded_params = path_params.union(query_params)
        
        # Add remaining arguments to body
        for key, value in arguments.items():
            if key not in excluded_params:
                body[key] = value
        
        return body if body else None
    
    def create_error_response(self, error_message: str, error_code: Optional[int] = None) -> Dict[str, Any]:
        """Create an MCP error response"""
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: {error_message}"
                }
            ],
            "isError": True,
            "_meta": {
                "error_code": error_code,
                "error_message": error_message
            }
        }

# Global request translator instance
request_translator = RequestTranslator()