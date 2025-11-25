from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
import models
from pathlib import Path
from fastapi.templating import Jinja2Templates
import bcrypt

router = APIRouter()

# Настройка путей для шаблонов
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def check_password(password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

# Зависимости для проверки ролей
def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Получение текущего пользователя из сессии"""
    user_id = request.session.get("user_id")
    if user_id:
        user = db.query(models.Customer).filter(models.Customer.id == user_id).first()
        if user and user.is_active:
            return user
    return None  # Гость

def require_auth(current_user: models.Customer = Depends(get_current_user)):
    """Требует аутентификации"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация"
        )
    return current_user

def require_admin(current_user: models.Customer = Depends(require_auth)):
    """Требует роль администратора"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав"
        )
    return current_user

# Роуты аутентификации
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(
    request: Request,
    db: Session = Depends(get_db)
):
    """Обработка входа"""
    form_data = await request.form()
    email = form_data.get("email")
    password = form_data.get("password")
    
    user = db.query(models.Customer).filter(models.Customer.email == email).first()
    
    if not user or not check_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверный email или пароль"
        })
    
    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Аккаунт деактивирован"
        })
    
    # Сохраняем пользователя в сессии
    request.session["user_id"] = user.id
    request.session["user_role"] = user.role
    request.session["user_name"] = user.name
    
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    """Страница регистрации"""
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register(
    request: Request,
    db: Session = Depends(get_db)
):
    """Обработка регистрации"""
    form_data = await request.form()
    email = form_data.get("email")
    password = form_data.get("password")
    name = form_data.get("name")
    
    # Проверяем, существует ли пользователь
    existing_user = db.query(models.Customer).filter(models.Customer.email == email).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Пользователь с таким email уже существует"
        })
    
    # Создаем нового пользователя
    new_user = models.Customer(
        email=email,
        name=name,
        role="customer"  # По умолчанию покупатель
    )
    new_user.hashed_password = hash_password(password)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Автоматически входим после регистрации
    request.session["user_id"] = new_user.id
    request.session["user_role"] = new_user.role
    request.session["user_name"] = new_user.name
    
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
def logout(request: Request):
    """Выход из системы"""
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

# Вспомогательные функции для работы с паролями
def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')