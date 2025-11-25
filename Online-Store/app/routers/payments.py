from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List
import json

from database import get_db
from models import Customer, Payment
from schemas.payment import PaymentCreate, PaymentResponse
from crud.payment import create_payment, get_payment, update_payment_status, get_payments_by_customer
from services.demo_payment import DemoPaymentService
from services.email_service import EmailService
from dependencies import get_current_customer

router = APIRouter(prefix="/payments", tags=["payments"])

payment_service = DemoPaymentService()
email_service = EmailService()

@router.post("/create", response_model=PaymentResponse)
async def create_payment_route(
    payment_data: PaymentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer)
):
    """Создание демо-платежа с немедленной отправкой чека"""
    
    try:
        print("=== PAYMENT CREATE CALLED ===")
        print(f"Payment data: {payment_data}")

        # Создаем запись платежа в БД
        db_payment = create_payment(db, payment_data, current_customer.id)
    
        # Сразу помечаем платеж как оплаченный
        update_payment_status(db, db_payment.id, "demo_paid")
    
        # Отправляем чек на email в фоне
        background_tasks.add_task(send_receipt_email, db, db_payment.id)
    
        response_data = PaymentResponse(
            id=db_payment.id,
            order_id=db_payment.order_id,
            amount=db_payment.amount,
            status="demo_paid",
            payment_url=f"/payments/success/{db_payment.id}",
            customer_email=db_payment.customer_email,
            payment_method=db_payment.payment_method
        )

        print(f"Payment created: {response_data}")
        return response_data
    
    except Exception as e:
        print(f"Error in create_payment_route: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/success/{payment_id}", response_class=HTMLResponse)
async def payment_success(
    payment_id: int,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer)
):
    """Страница успешной оплаты"""
    
    payment = get_payment(db, payment_id)
    if not payment or payment.customer_id != current_customer.id:
        raise HTTPException(status_code=404, detail="Платеж не найден")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Оплата успешна | TechTown</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .success-card {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 500px;
                width: 100%;
            }}
            .success-icon {{
                font-size: 80px;
                color: #27ae60;
                margin-bottom: 20px;
            }}
            .email-notification {{
                background: #e8f5e8;
                border: 1px solid #27ae60;
                border-radius: 10px;
                padding: 15px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="success-card">
            <div class="success-icon">✅</div>
            <h1 class="mb-3">Оплата прошла успешно!</h1>
            <div class="email-notification">
                <h5><i class="fas fa-envelope me-2"></i>Чек отправлен</h5>
                <p class="mb-0">Чек по заказу №{payment.order_id} отправлен на вашу почту:</p>
                <strong>{payment.customer_email}</strong>
            </div>
            <div class="mb-4">
                <p><strong>Сумма оплаты:</strong> {payment.amount} ₽</p>
                <p><strong>Способ оплаты:</strong> {payment.payment_method}</p>
                <p class="text-muted"><em>Это демо-платеж. Реальные деньги не списывались.</em></p>
            </div>
            <div class="d-grid gap-2">
                <a href="/" class="btn btn-primary btn-lg">
                    <i class="fas fa-home me-2"></i>Вернуться в магазин
                </a>
                <a href="/products/" class="btn btn-outline-primary">
                    <i class="fas fa-shopping-bag me-2"></i>Продолжить покупки
                </a>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

async def send_receipt_email(db: Session, payment_id: int):
    """Отправка чека на email"""
    try:
        payment = get_payment(db, payment_id)
        if not payment:
            print(f"Payment {payment_id} not found for receipt")
            return
        
        # Подготавливаем данные для чека
        receipt_data = {
            "payment_id": payment.id,
            "payment_date": payment.created_at.strftime("%d.%m.%Y %H:%M"),
            "order_id": payment.order_id,
            "customer_email": payment.customer_email,
            "customer_phone": payment.customer_phone,
            "payment_method": payment.payment_method,
            "items": json.loads(payment.items_json),
            "total_amount": payment.amount
        }
        
        print(f"Sending receipt to {payment.customer_email}")
        # Отправляем чек
        email_service.send_receipt(payment.customer_email, receipt_data)
    except Exception as e:
        print(f"Error sending receipt: {e}")
    

@router.get("/{payment_id}")
async def get_payment_status(
    payment_id: int,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer)
):
    """Получить статус платежа"""
    payment = get_payment(db, payment_id)
    if not payment or payment.customer_id != current_customer.id:
        raise HTTPException(status_code=404, detail="Платеж не найден")
    
    return payment

@router.get("/customer/my", response_model=List[PaymentResponse])
async def get_my_payments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer)
):
    """Получить платежи текущего пользователя"""
    payments = get_payments_by_customer(db, current_customer.id, skip, limit)
    return payments