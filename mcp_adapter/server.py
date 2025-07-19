from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import json
import asyncio
import uuid
from typing import Dict, Any, Optional
import logging

# Import our new components
from .tool_generator import get_tool_generator
from .tool_executor import get_tool_executor
from .request_translator import request_translator
from .http_client import http_client
from .service_discovery import service_discovery
from .openapi_loader import openapi_loader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Adapter", version="1.0.0")

# Session management
sessions: Dict[str, Dict[str, Any]] = {}

class MCPServer:
    def __init__(self):
        self.capabilities = {
            "tools": {},
            "resources": {},
            "prompts": {}
        }
        self.is_initialized = False
        self.tool_generator = None
        self.tool_executor = None
        
    async def initialize_components(self):
        """Initialize all components - called during startup"""
        if self.is_initialized:
            return
        
        logger.info("Initializing MCP server components...")
        
        try:
            # Initialize HTTP client
            await http_client.initialize()
            
            # Start service discovery
            await service_discovery.start_monitoring()
            
            # Start OpenAPI loader
            await openapi_loader.start_loading()
            
            # Wait a bit for services to be discovered
            await asyncio.sleep(2)
            
            # Initialize tool generator
            self.tool_generator = get_tool_generator(openapi_loader, service_discovery)
            
            # Generate tools from OpenAPI specs
            tools = self.tool_generator.generate_all_tools()
            logger.info(f"Generated {len(tools)} tools from OpenAPI specs")
            
            # Initialize tool executor
            self.tool_executor = get_tool_executor(self.tool_generator, http_client, request_translator)
            
            # Update capabilities
            self.capabilities["tools"] = {
                "listChanged": True
            }
            
            self.is_initialized = True
            logger.info("MCP server initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP server: {e}")
            raise
    
    async def handle_initialize(self, params: dict) -> dict:
        """Handle MCP initialize request"""
        protocol_version = params.get("protocolVersion", "2024-11-05")
        client_info = params.get("clientInfo", {})
        
        logger.info(f"Initialize request from {client_info}")
        
        # Initialize components if not already done
        if not self.is_initialized:
            await self.initialize_components()
        
        return {
            "protocolVersion": protocol_version,
            "capabilities": self.capabilities,
            "serverInfo": {
                "name": "mcp-adapter",
                "version": "1.0.0"
            }
        }
    
    async def handle_tools_list(self, params: dict) -> dict:
        """Handle tools/list request"""
        if not self.is_initialized:
            await self.initialize_components()
        
        if self.tool_executor:
            tools = await self.tool_executor.list_available_tools()
            return {"tools": tools}
        else:
            return {"tools": []}
    
    async def handle_tools_call(self, params: dict) -> dict:
        """Handle tools/call request"""
        if not self.is_initialized:
            await self.initialize_components()
        
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            raise HTTPException(
                status_code=400,
                detail="Tool name is required"
            )
        
        if not self.tool_executor:
            raise HTTPException(
                status_code=503,
                detail="Tool executor not initialized"
            )
        
        # Execute the tool
        result = await self.tool_executor.execute_tool(tool_name, arguments)
        
        return result
    
    async def shutdown(self):
        """Shutdown all components"""
        logger.info("Shutting down MCP server components...")
        
        if service_discovery:
            await service_discovery.stop_monitoring()
        
        if openapi_loader:
            await openapi_loader.stop_loading()
        
        if http_client:
            await http_client.close()
        
        logger.info("MCP server shutdown complete")

mcp_server = MCPServer()

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """Handle MCP requests over HTTP"""
    
    # Extract session ID from headers
    session_id = request.headers.get("Mcp-Session-Id")
    
    try:
        # Parse JSON-RPC message from HTTP body
        body = await request.body()
        jsonrpc_message = json.loads(body)
        
        # Validate JSON-RPC structure
        if jsonrpc_message.get("jsonrpc") != "2.0":
            return create_error_response(
                None, -32600, "Invalid JSON-RPC version"
            )
        
        method = jsonrpc_message.get("method")
        params = jsonrpc_message.get("params", {})
        request_id = jsonrpc_message.get("id")
        
        logger.info(f"Received {method} request: {params}")
        
        # Route to appropriate handler
        if method == "initialize":
            result = await mcp_server.handle_initialize(params)
            
            # Create session if not exists
            if not session_id:
                session_id = str(uuid.uuid4())
                sessions[session_id] = {
                    "created_at": asyncio.get_event_loop().time(),
                    "client_info": params.get("clientInfo", {})
                }
            
            response = create_success_response(request_id, result)
            json_response = JSONResponse(response)
            
            # Set session ID in response header
            json_response.headers["Mcp-Session-Id"] = session_id
            return json_response
            
        elif method == "notifications/initialized":
            # Just acknowledge
            logger.info(f"Session {session_id} initialized")
            return JSONResponse({"status": "ok"})
            
        elif method == "tools/list":
            result = await mcp_server.handle_tools_list(params)
            return create_success_response(request_id, result)
            
        elif method == "tools/call":
            result = await mcp_server.handle_tools_call(params)
            return create_success_response(request_id, result)
            
        else:
            return create_error_response(
                request_id, -32601, f"Method not found: {method}"
            )
            
    except json.JSONDecodeError:
        return create_error_response(None, -32700, "Parse error")
    except Exception as e:
        logger.error(f"Internal error: {e}")
        return create_error_response(
            jsonrpc_message.get("id"), -32603, "Internal error"
        )

def create_success_response(request_id: Any, result: Any) -> dict:
    """Create JSON-RPC success response"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }

def create_error_response(request_id: Any, code: int, message: str) -> dict:
    """Create JSON-RPC error response"""
    return {
        "jsonrpc": "2.0", 
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint with detailed status"""
    if mcp_server.is_initialized:
        # Get detailed health info
        if mcp_server.tool_executor:
            tool_health = await mcp_server.tool_executor.health_check()
            return {
                "status": "healthy",
                "service": "mcp-adapter",
                "details": tool_health
            }
        else:
            return {
                "status": "healthy",
                "service": "mcp-adapter", 
                "details": {"tools_available": 0}
            }
    else:
        return {
            "status": "initializing",
            "service": "mcp-adapter"
        }

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    logger.info("Starting MCP Adapter server...")
    try:
        await mcp_server.initialize_components()
        logger.info("MCP Adapter server started successfully")
    except Exception as e:
        logger.error(f"Failed to start MCP Adapter server: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down MCP Adapter server...")
    await mcp_server.shutdown()
    logger.info("MCP Adapter server shut down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)