from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, EmailStr, validator
from typing import List, Optional, Dict
import uvicorn
from datetime import datetime
import re

app = FastAPI(title="Customer Service", version="1.0.0")

class Customer(BaseModel):
    id: str = Field(..., pattern="^cust-[0-9]{3,}$", description="Customer ID in format cust-XXX")
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, pattern="^\\+?[1-9][\\d\\-\\s]{1,14}$")
    status: str = Field("active", pattern="^(active|inactive|suspended)$")
    created_at: str
    
    @validator('name')
    def validate_name(cls, v):
        if not re.match("^[a-zA-Z\\s'-]+$", v):
            raise ValueError('Name must contain only letters, spaces, hyphens, and apostrophes')
        return v

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern="^\\+?[1-9][\\d\\-\\s]{1,14}$")
    status: Optional[str] = Field(None, pattern="^(active|inactive|suspended)$")
    
    @validator('name')
    def validate_name(cls, v):
        if v and not re.match("^[a-zA-Z\\s'-]+$", v):
            raise ValueError('Name must contain only letters, spaces, hyphens, and apostrophes')
        return v

# Mock data store
customers_db = {
    "cust-001": Customer(
        id="cust-001", 
        name="John Doe", 
        email="john@example.com",
        phone="+1-555-0123",
        status="active",
        created_at="2024-01-15T10:30:00Z"
    ),
    "cust-002": Customer(
        id="cust-002",
        name="Jane Smith", 
        email="jane@example.com",
        status="active", 
        created_at="2024-02-20T14:45:00Z"
    )
}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "customer-api"}

@app.get("/customers/{customer_id}", response_model=Customer)
async def get_customer(customer_id: str):
    if customer_id not in customers_db:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customers_db[customer_id]

@app.get("/customers", response_model=List[Customer]) 
async def list_customers(limit: int = Query(10, ge=1, le=100), status: str = None):
    customers = list(customers_db.values())
    if status:
        if status not in ["active", "inactive", "suspended"]:
            raise HTTPException(status_code=400, detail="Invalid status value")
        customers = [c for c in customers if c.status == status]
    return customers[:limit]

@app.post("/customers", response_model=Customer)
async def create_customer(customer: Customer):
    customers_db[customer.id] = customer
    return customer

@app.put("/customers/{customer_id}", response_model=Customer)
async def update_customer(customer_id: str, updates: CustomerUpdate):
    if customer_id not in customers_db:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer = customers_db[customer_id]
    update_data = updates.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    return customer

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)