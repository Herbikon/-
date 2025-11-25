from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
import json

from database import get_db
from models import Customer
from dependencies import get_current_customer

router = APIRouter()

# Настройка путей для шаблонов
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/checkout/", response_class=HTMLResponse)
async def checkout_page(
    request: Request,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer)
):
    """Страница оформления заказа"""
    
    return templates.TemplateResponse("checkout.html", {
        "request": request,
        "current_user": current_customer
    })