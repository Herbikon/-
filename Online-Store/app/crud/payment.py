from sqlalchemy.orm import Session
from typing import List, Optional
import json
from models import Payment
from schemas.payment import PaymentCreate

def create_payment(db: Session, payment: PaymentCreate, customer_id: int) -> Payment:
    db_payment = Payment(
        order_id=payment.order_id,
        customer_id=customer_id,
        amount=payment.amount,
        customer_email=payment.customer_email,
        customer_phone=payment.customer_phone,
        description=payment.description,
        payment_method=payment.payment_method,
        items_json=json.dumps([item.dict() for item in payment.items])
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

def get_payment(db: Session, payment_id: int) -> Optional[Payment]:
    return db.query(Payment).filter(Payment.id == payment_id).first()

def update_payment_status(db: Session, payment_id: int, status: str) -> Optional[Payment]:
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment:
        payment.status = status
        db.commit()
        db.refresh(payment)
    return payment

def get_payments_by_customer(db: Session, customer_id: int, skip: int = 0, limit: int = 100) -> List[Payment]:
    return db.query(Payment).filter(Payment.customer_id == customer_id).offset(skip).limit(limit).all()