#!/bin/bash

# MCP → REST Pattern: Quick Start Script
# This script sets up and runs the complete MCP adapter system

set -e  # Exit on any error

echo "🚀 MCP → REST Pattern Quick Start"
echo "================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
    if [[ $(echo "$python_version < 3.8" | bc) -eq 1 ]]; then
        print_error "Python 3.8+ is required, found $python_version"
        exit 1
    fi
    print_status "Python $python_version ✓"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is required but not installed"
        exit 1
    fi
    print_status "Docker $(docker --version | cut -d' ' -f3 | cut -d',' -f1) ✓"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is required but not installed"
        exit 1
    fi
    print_status "Docker Compose $(docker-compose --version | cut -d' ' -f3 | cut -d',' -f1) ✓"
}

# Setup virtual environment
setup_venv() {
    print_status "Setting up Python virtual environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_status "Created virtual environment ✓"
    else
        print_status "Virtual environment already exists ✓"
    fi
    
    source venv/bin/activate
    print_status "Activated virtual environment ✓"
    
    # Upgrade pip
    pip install --upgrade pip > /dev/null 2>&1
    print_status "Updated pip ✓"
    
    # Install dependencies
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt > /dev/null 2>&1
        print_status "Installed main dependencies ✓"
    fi
    
    if [ -f "requirements-dev.txt" ]; then
        pip install -r requirements-dev.txt > /dev/null 2>&1
        print_status "Installed development dependencies ✓"
    fi
}

# Start Docker services
start_services() {
    print_status "Starting mock backend services..."
    
    # Pull images
    docker-compose pull > /dev/null 2>&1
    print_status "Pulled Docker images ✓"
    
    # Start services
    docker-compose up -d
    print_status "Started Docker services ✓"
    
    # Wait for services to be ready
    print_status "Waiting for services to be ready..."
    sleep 15
    
    # Check service health
    services=("customer-service:8001" "order-service:8002" "inventory-service:8003")
    for service in "${services[@]}"; do
        IFS=':' read -r name port <<< "$service"
        if curl -s -f "http://localhost:$port/health" > /dev/null; then
            print_status "$name is healthy ✓"
        else
            print_error "$name is not responding"
            exit 1
        fi
    done
}

# Run tests
run_tests() {
    print_status "Running tests..."
    
    source venv/bin/activate
    
    # Run unit tests
    if pytest tests/unit/ -v > test_results.log 2>&1; then
        print_status "Unit tests passed ✓"
    else
        print_error "Unit tests failed - check test_results.log"
        return 1
    fi
    
    # Run integration tests
    if pytest tests/integration/ -v >> test_results.log 2>&1; then
        print_status "Integration tests passed ✓"
    else
        print_error "Integration tests failed - check test_results.log"
        return 1
    fi
    
    print_status "All tests passed ✓"
}

# Start MCP adapter
start_mcp_adapter() {
    print_status "Starting MCP adapter..."
    
    source venv/bin/activate
    
    # Start MCP adapter in background
    python -m mcp_adapter.server > mcp_adapter.log 2>&1 &
    MCP_PID=$!
    
    # Wait for MCP adapter to start
    sleep 10
    
    # Check if MCP adapter is running
    if curl -s -f "http://localhost:8000/health" > /dev/null; then
        print_status "MCP adapter is running ✓"
        echo "MCP Adapter PID: $MCP_PID"
    else
        print_error "MCP adapter failed to start - check mcp_adapter.log"
        exit 1
    fi
}

# Test MCP functionality
test_mcp_functionality() {
    print_status "Testing MCP functionality..."
    
    # Test initialization
    init_response=$(curl -s -X POST http://localhost:8000/mcp \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "quick-start-test", "version": "1.0.0"}
            }
        }')
    
    if echo "$init_response" | jq -e '.result.capabilities' > /dev/null; then
        print_status "MCP initialization successful ✓"
    else
        print_error "MCP initialization failed"
        echo "$init_response"
        return 1
    fi
    
    # Test tools list
    tools_response=$(curl -s -X POST http://localhost:8000/mcp \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }')
    
    tool_count=$(echo "$tools_response" | jq '.result.tools | length')
    if [ "$tool_count" -gt 0 ]; then
        print_status "Found $tool_count tools ✓"
    else
        print_error "No tools found"
        echo "$tools_response"
        return 1
    fi
    
    # Test tool execution
    execute_response=$(curl -s -X POST http://localhost:8000/mcp \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "customer_getCustomers",
                "arguments": {}
            }
        }')
    
    if echo "$execute_response" | jq -e '.result.isError == false' > /dev/null; then
        print_status "Tool execution successful ✓"
    else
        print_error "Tool execution failed"
        echo "$execute_response"
        return 1
    fi
    
    print_status "All MCP functionality tests passed ✓"
}

# Display system status
show_status() {
    echo
    echo "🎯 System Status"
    echo "==============="
    
    # Docker services
    echo "Docker Services:"
    docker-compose ps
    
    echo
    echo "Service Health:"
    curl -s http://localhost:8001/health | jq '.status' | xargs echo "Customer Service:"
    curl -s http://localhost:8002/health | jq '.status' | xargs echo "Order Service:"
    curl -s http://localhost:8003/health | jq '.status' | xargs echo "Inventory Service:"
    curl -s http://localhost:8000/health | jq '.status' | xargs echo "MCP Adapter:"
    
    echo
    echo "MCP Adapter Details:"
    curl -s http://localhost:8000/health | jq '.details'
    
    echo
    echo "📡 Access URLs:"
    echo "- Customer Service: http://localhost:8001"
    echo "- Order Service: http://localhost:8002"
    echo "- Inventory Service: http://localhost:8003"
    echo "- MCP Adapter: http://localhost:8000"
    echo "- Health Check: http://localhost:8000/health"
    
    echo
    echo "📖 Example MCP Request:"
    echo 'curl -X POST http://localhost:8000/mcp \'
    echo '  -H "Content-Type: application/json" \'
    echo '  -d '"'"'{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'"'"''
}

# Cleanup function
cleanup() {
    echo
    print_status "Cleaning up..."
    
    # Stop MCP adapter if running
    if [ ! -z "$MCP_PID" ]; then
        kill $MCP_PID > /dev/null 2>&1
        print_status "Stopped MCP adapter"
    fi
    
    # Stop Docker services
    docker-compose down > /dev/null 2>&1
    print_status "Stopped Docker services"
}

# Main execution
main() {
    # Parse command line arguments
    RUN_TESTS=false
    CLEANUP_ONLY=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --test)
                RUN_TESTS=true
                shift
                ;;
            --cleanup)
                CLEANUP_ONLY=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --test     Run tests after setup"
                echo "  --cleanup  Only cleanup and exit"
                echo "  --help     Show this help"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Handle cleanup-only mode
    if [ "$CLEANUP_ONLY" = true ]; then
        cleanup
        exit 0
    fi
    
    # Trap cleanup on exit
    trap cleanup EXIT
    
    # Run setup steps
    check_prerequisites
    setup_venv
    start_services
    
    # Run tests if requested
    if [ "$RUN_TESTS" = true ]; then
        run_tests
    fi
    
    # Start MCP adapter
    start_mcp_adapter
    
    # Test MCP functionality
    test_mcp_functionality
    
    # Show system status
    show_status
    
    echo
    print_status "🎉 Setup complete! System is ready for use."
    echo
    echo "To stop the system, run: $0 --cleanup"
    echo "Or press Ctrl+C to stop all services."
    echo
    echo "Check the setup guide for more details: SETUP_AND_TESTING_GUIDE.md"
    
    # Keep script running
    echo "Press Ctrl+C to stop..."
    while true; do
        sleep 60
    done
}

# Run main function
main "$@"