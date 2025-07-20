# MCP → REST Adapter

Make your existing REST APIs instantly accessible to AI agents (Claude, GPT-4, etc.) without changing a single line of code.

## 🚀 Quick Start (5 minutes)

```bash
# Clone the repository
git clone https://github.com/deepwissen/mcp_rest_adapter.git
cd mcp_rest_adapter

# Start everything with one command
./quick_start.sh
```

That's it! Your REST APIs are now AI-accessible. Test it:

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}'
```

## 🎯 What This Does

The MCP Adapter acts as a bridge between AI agents and your existing microservices:

```
AI Agent (Claude/GPT) → MCP Protocol → MCP Adapter → Your REST APIs
```

**Before**: Months of custom AI integration code  
**After**: 5 minutes to AI-enable your entire API ecosystem

## 🛠️ Manual Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Your REST APIs with OpenAPI/Swagger specs

### Step 1: Configure Your Services

Edit `docker-compose.yml` to point to your services:

```yaml
environment:
  - CUSTOMER_SERVICE_URL=http://your-customer-api:8080
  - ORDER_SERVICE_URL=http://your-order-api:8080
  - INVENTORY_SERVICE_URL=http://your-inventory-api:8080
```

### Step 2: Start the Adapter

```bash
# Start with Docker Compose
docker-compose up -d

# Or run directly with Python
pip install -r requirements.txt
python -m uvicorn mcp_adapter.server:app --port 8000
```

### Step 3: Verify It's Working

```bash
# Check health
curl http://localhost:8000/health

# List available tools (auto-generated from your APIs)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}'
```

## 📋 Requirements for Your APIs

Your REST APIs need:
1. **Health endpoint** (`/health`) that returns 200 OK
2. **OpenAPI spec** (`/openapi.json` or `/swagger.json`)
3. **Standard REST patterns** (GET, POST, PUT, DELETE)

That's it. No code changes required.

## 🔧 Configuration

Create a `config.py` file:

```python
SERVICE_CONFIGS = {
    "customer": {
        "base_url": "http://customer-service:8001",
        "health_endpoint": "/health",
        "openapi_endpoint": "/openapi.json"
    },
    "order": {
        "base_url": "http://order-service:8002",
        "health_endpoint": "/health",
        "openapi_endpoint": "/openapi.json"
    }
}
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
./run_tests.py

# Run with Docker
docker-compose -f docker-compose.test.yml up
```

## 📊 What You Get

Once running, AI agents can:
- Discover all your API endpoints automatically
- Call any endpoint with proper parameters
- Handle complex workflows across multiple services
- Get structured responses in MCP format

Example: An AI agent can now say "Show me all orders for customer John Doe" and automatically:
1. Search for the customer
2. Get their customer ID
3. Fetch all orders
4. Return formatted results

## 🚨 Troubleshooting

**Services not discovered?**
- Check your services have `/health` endpoints returning 200 OK
- Verify `/openapi.json` is accessible

**No tools generated?**
- Ensure your OpenAPI spec is valid
- Check logs: `docker-compose logs mcp-adapter`

**Connection errors?**
- Verify network connectivity between adapter and your services
- Check service URLs in configuration

## 🤝 Contributing

We welcome contributions! Please check out our [Contributing Guide](CONTRIBUTING.md).

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

- [Documentation](https://github.com/deepwissen/mcp_rest_adapter/wiki)
- [Issues](https://github.com/deepwissen/mcp_rest_adapter/issues)
- [Discussions](https://github.com/deepwissen/mcp_rest_adapter/discussions)

---

**Built with ❤️ to make AI integration simple**