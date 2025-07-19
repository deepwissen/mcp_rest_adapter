from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from datetime import datetime

app = FastAPI(title="Inventory Service", version="1.0.0")

class Product(BaseModel):
    id: str
    name: str
    sku: str
    quantity: int
    price: float
    status: str = "available"
    updated_at: str

# Mock data
inventory_db = {
    "prod-1": Product(
        id="prod-1",
        name="Widget A",
        sku="WGT-A-001",
        quantity=100,
        price=29.99,
        status="available",
        updated_at="2024-01-15T10:30:00Z"
    ),
    "prod-2": Product(
        id="prod-2",
        name="Widget B",
        sku="WGT-B-001",
        quantity=50,
        price=49.99,
        status="available",
        updated_at="2024-01-15T10:30:00Z"
    )
}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "inventory-api"}

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    if product_id not in inventory_db:
        raise HTTPException(status_code=404, detail="Product not found")
    return inventory_db[product_id]

@app.get("/products", response_model=List[Product])
async def list_products(status: str = None, limit: int = 10):
    products = list(inventory_db.values())
    if status:
        products = [p for p in products if p.status == status]
    return products[:limit]

@app.put("/products/{product_id}/quantity", response_model=Product)
async def update_quantity(product_id: str, quantity: int):
    if product_id not in inventory_db:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product = inventory_db[product_id]
    product.quantity = quantity
    product.updated_at = datetime.utcnow().isoformat() + "Z"
    
    return product

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)