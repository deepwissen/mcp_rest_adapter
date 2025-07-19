import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add the mock-services directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../mock-services'))

from mock_customer_service import app, Customer, customers_db

@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)

@pytest.fixture(autouse=True)
def reset_database():
    """Reset the database before each test"""
    # Store original state
    original_db = customers_db.copy()
    yield
    # Restore original state
    customers_db.clear()
    customers_db.update(original_db)

class TestCustomerService:
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "customer-api"}
    
    def test_get_customer_success(self, client):
        """Test getting an existing customer"""
        response = client.get("/customers/cust-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "cust-001"
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"
    
    def test_get_customer_not_found(self, client):
        """Test getting a non-existent customer"""
        response = client.get("/customers/cust-999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"
    
    def test_list_customers_no_filters(self, client):
        """Test listing all customers"""
        response = client.get("/customers")
        assert response.status_code == 200
        customers = response.json()
        assert len(customers) == 2
        assert all(isinstance(c, dict) for c in customers)
    
    def test_list_customers_with_limit(self, client):
        """Test listing customers with limit"""
        response = client.get("/customers?limit=1")
        assert response.status_code == 200
        customers = response.json()
        assert len(customers) == 1
    
    def test_list_customers_invalid_limit(self, client):
        """Test listing customers with invalid limit"""
        response = client.get("/customers?limit=101")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/customers?limit=0")
        assert response.status_code == 422  # Validation error
    
    def test_list_customers_with_status_filter(self, client):
        """Test listing customers with status filter"""
        response = client.get("/customers?status=active")
        assert response.status_code == 200
        customers = response.json()
        assert all(c["status"] == "active" for c in customers)
    
    def test_list_customers_invalid_status(self, client):
        """Test listing customers with invalid status"""
        response = client.get("/customers?status=invalid")
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid status value"
    
    def test_create_customer_success(self, client):
        """Test creating a new customer"""
        new_customer = {
            "id": "cust-003",
            "name": "Alice Johnson",
            "email": "alice@example.com",
            "phone": "+1234567890",
            "status": "active",
            "created_at": "2024-03-01T10:00:00Z"
        }
        response = client.post("/customers", json=new_customer)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "cust-003"
        assert data["name"] == "Alice Johnson"
        
        # Verify customer was added to database
        assert "cust-003" in customers_db
    
    def test_create_customer_invalid_data(self, client):
        """Test creating customer with invalid data"""
        # Invalid email
        invalid_customer = {
            "id": "cust-003",
            "name": "Alice Johnson",
            "email": "invalid-email",
            "status": "active",
            "created_at": "2024-03-01T10:00:00Z"
        }
        response = client.post("/customers", json=invalid_customer)
        assert response.status_code == 422
        
        # Invalid ID format
        invalid_customer = {
            "id": "invalid-id",
            "name": "Alice Johnson",
            "email": "alice@example.com",
            "status": "active",
            "created_at": "2024-03-01T10:00:00Z"
        }
        response = client.post("/customers", json=invalid_customer)
        assert response.status_code == 422
        
        # Invalid name (contains numbers)
        invalid_customer = {
            "id": "cust-003",
            "name": "Alice123",
            "email": "alice@example.com",
            "status": "active",
            "created_at": "2024-03-01T10:00:00Z"
        }
        response = client.post("/customers", json=invalid_customer)
        assert response.status_code == 422
    
    def test_update_customer_success(self, client):
        """Test updating an existing customer"""
        update_data = {
            "name": "John Updated",
            "email": "john.updated@example.com"
        }
        response = client.put("/customers/cust-001", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "John Updated"
        assert data["email"] == "john.updated@example.com"
        assert data["id"] == "cust-001"  # ID should not change
    
    def test_update_customer_not_found(self, client):
        """Test updating a non-existent customer"""
        update_data = {"name": "New Name"}
        response = client.put("/customers/cust-999", json=update_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"
    
    def test_update_customer_partial_update(self, client):
        """Test partial update of customer"""
        # Update only the status
        update_data = {"status": "inactive"}
        response = client.put("/customers/cust-001", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "inactive"
        assert data["name"] == "John Doe"  # Other fields unchanged
        assert data["email"] == "john@example.com"
    
    def test_update_customer_invalid_data(self, client):
        """Test updating customer with invalid data"""
        # Invalid status
        update_data = {"status": "invalid-status"}
        response = client.put("/customers/cust-001", json=update_data)
        assert response.status_code == 422
        
        # Invalid email
        update_data = {"email": "not-an-email"}
        response = client.put("/customers/cust-001", json=update_data)
        assert response.status_code == 422
    
    def test_phone_validation(self, client):
        """Test phone number validation"""
        # Valid phone numbers
        valid_phones = ["+1234567890", "1234567890", "+442079460958"]
        for phone in valid_phones:
            customer = {
                "id": f"cust-{phone[:4]}",
                "name": "Test User",
                "email": "test@example.com",
                "phone": phone,
                "status": "active",
                "created_at": "2024-03-01T10:00:00Z"
            }
            response = client.post("/customers", json=customer)
            assert response.status_code == 200, f"Failed for phone: {phone}"
        
        # Invalid phone numbers
        invalid_phones = ["123", "abcdefghij", "+0123456789", ""]
        for phone in invalid_phones:
            customer = {
                "id": "cust-999",
                "name": "Test User",
                "email": "test@example.com",
                "phone": phone,
                "status": "active",
                "created_at": "2024-03-01T10:00:00Z"
            }
            response = client.post("/customers", json=customer)
            assert response.status_code == 422, f"Should have failed for phone: {phone}"