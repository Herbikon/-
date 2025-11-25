from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from fastapi.templating import Jinja2Templates
import models

router = APIRouter()

templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
@router.post("/add-to-cart/")
def add_to_cart(product_id: int, quantity: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if product.stock_quantity < quantity:
        raise HTTPException(status_code=400, detail="Недостаточно товара на складе")
    # Логика добавления в корзину
    product.stock_quantity -= quantity
    db.commit()
    return {"message": "Товар добавлен в корзину"}

@router.get("/")
def list_products(
    request: Request, 
    category_id: int | None = None, 
    db: Session = Depends(get_db)
):
    try:
        query = db.query(models.Product).filter(models.Product.stock_quantity > 0)
        if category_id:
            query = query.filter(models.Product.category_id == category_id)
        products = query.all()
        
        categories = db.query(models.Category).all()
        
        return templates.TemplateResponse(
            "products.html", 
            {
                "request": request, 
                "products": products,
                "categories": categories
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
