from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Request
from sqlalchemy.orm import Session
from database import get_db
import models
from pathlib import Path
import shutil
import time
from fastapi.templating import Jinja2Templates

router = APIRouter()

# Добавим templates
templates = Jinja2Templates(directory="templates")

@router.get("/products")
def admin_products(
    request: Request,
    db: Session = Depends(get_db),
    category_id: int = None
):
    categories = db.query(models.Category).all()
    products = db.query(models.Product)
    
    if category_id:
        products = products.filter(models.Product.category_id == category_id)
    
    products = products.all()
    
    return templates.TemplateResponse("admin_products.html", {
        "request": request,
        "products": products,
        "categories": categories
    })

@router.post("/products")
def create_product(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category_id: int = Form(...),
    stock_quantity: int = Form(0),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Сохраняем изображение если есть
    image_url = None
    if image and image.filename:
        upload_dir = Path("static/uploads")
        upload_dir.mkdir(exist_ok=True)
        
        file_location = upload_dir / f"product_{int(time.time())}_{image.filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        
        image_url = f"/static/uploads/{file_location.name}"
    
    # Создаем продукт
    product = models.Product(
        name=name,
        description=description,
        price=price,
        category_id=category_id,
        stock_quantity=stock_quantity,
        image_url=image_url
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return {"message": "Товар успешно добавлен", "product_id": product.id}

@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    category_id: int = Form(...),
    stock_quantity: int = Form(...),
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    product.name = name
    product.description = description
    product.price = price
    product.category_id = category_id
    product.stock_quantity = stock_quantity
    
    db.commit()
    
    return {"message": "Товар успешно обновлен"}

@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    db.delete(product)
    db.commit()
    
    return {"message": "Товар успешно удален"}