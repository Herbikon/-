from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Customer

def get_current_customer(db: Session = Depends(get_db)):
    """Получить текущего пользователя (упрощенная версия для демо)"""
    
    # Пытаемся найти первого пользователя в базе
    customer = db.query(Customer).first()
    
    if not customer:
        # Если пользователей нет, создаем демо-пользователя
        customer = Customer(
            email="demo@techtown.ru",
            first_name="Демо",
            last_name="Пользователь",
            role="customer"
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
    
    return customer
