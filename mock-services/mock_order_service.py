from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
import uvicorn
from datetime import datetime

app = FastAPI(title="Order Service", version="1.0.0")

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed" 
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float

class Order(BaseModel):
    id: str
    customer_id: str
    items: List[OrderItem]
    status: OrderStatus
    total_amount: float
    created_at: str
    updated_at: str

# Mock data
orders_db = {
    "order-001": Order(
        id="order-001",
        customer_id="cust-001",
        items=[
            OrderItem(product_id="prod-1", product_name="Widget A", quantity=2, unit_price=29.99),
            OrderItem(product_id="prod-2", product_name="Widget B", quantity=1, unit_price=49.99)
        ],
        status=OrderStatus.CONFIRMED,
        total_amount=109.97,
        created_at="2024-01-16T09:15:00Z",
        updated_at="2024-01-16T10:30:00Z"
    )
}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "order-api"}

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders_db[order_id]

@app.get("/orders", response_model=List[Order])
async def list_orders(customer_id: str = None, status: OrderStatus = None, limit: int = 10):
    orders = list(orders_db.values())
    
    if customer_id:
        orders = [o for o in orders if o.customer_id == customer_id]
    if status:
        orders = [o for o in orders if o.status == status]
        
    return orders[:limit]

@app.post("/orders", response_model=Order)
async def create_order(order: Order):
    order.created_at = datetime.utcnow().isoformat() + "Z"
    order.updated_at = order.created_at
    orders_db[order.id] = order
    return order

@app.put("/orders/{order_id}/status", response_model=Order)
async def update_order_status(order_id: str, status: OrderStatus, notes: str = None):
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[order_id]
    order.status = status
    order.updated_at = datetime.utcnow().isoformat() + "Z"
    
    return order

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)