from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class PaymentItem(BaseModel):
    name: str
    quantity: int
    price: float
    category: str

class PaymentCreate(BaseModel):
    order_id: int
    customer_email: EmailStr
    customer_phone: Optional[str] = None
    amount: float
    items: List[PaymentItem]
    description: Optional[str] = None
    payment_method: Optional[str] = "demo_card"  # demo_card, demo_sbp

class PaymentResponse(BaseModel):
    id: int
    order_id: int
    amount: float
    status: str
    payment_url: Optional[str] = None
    customer_email: str
    payment_method: str
    
    class Config:
        from_attributes = True

class DemoPaymentRequest(BaseModel):
    payment_id: int
    action: str  # confirm, cancel