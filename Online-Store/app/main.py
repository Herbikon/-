import os
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException, Cookie, Response, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
import secrets
from datetime import datetime, timedelta
from starlette.middleware.sessions import SessionMiddleware
import bcrypt
import time
from collections import defaultdict
import re

BASE_DIR = Path(__file__).resolve().parent

from database import SessionLocal, engine
import models
from routers import reports, admin, auth, payments, checkout

# ==================== DDoS ЗАЩИТА ====================

# 1. СИСТЕМА ОГРАНИЧЕНИЯ ЧАСТОТЫ ЗАПРОСОВ
class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.max_requests_per_minute = 60  # Максимум 60 запросов в минуту
        self.blocked_ips = {}
        self.block_duration = 300  # Блокировка на 5 минут
    
    def is_rate_limited(self, ip: str) -> bool:
        """Проверяет, не превышен ли лимит запросов для IP"""
        current_time = time.time()
        
        # Проверяем, не заблокирован ли IP
        if ip in self.blocked_ips:
            if current_time < self.blocked_ips[ip]:
                return True
            else:
                del self.blocked_ips[ip]
        
        # Очищаем старые записи (старше 1 минуты)
        self.requests[ip] = [req_time for req_time in self.requests[ip] 
                           if current_time - req_time < 60]
        
        # Проверяем лимит
        if len(self.requests[ip]) >= self.max_requests_per_minute:
            # Блокируем IP на 5 минут
            self.blocked_ips[ip] = current_time + self.block_duration
            print(f"🚨 IP {ip} заблокирован за превышение лимита запросов")
            return True
        
        # Добавляем текущий запрос
        self.requests[ip].append(current_time)
        return False

# 2. ФИЛЬТРАЦИЯ ПОЛЬЗОВАТЕЛЬСКИХ АГЕНТОВ
class UserAgentFilter:
    def __init__(self):
        # Список подозрительных/нежелательных User-Agent
        self.suspicious_agents = [
            "bot", "crawler", "spider", "scraper", "python", "curl", 
            "wget", "masscan", "sqlmap", "nikto", "zmeu", "acunetix",
            "xenu", "nessus", "nmap", "megaindex", "mail.ru", "yandexbot"
        ]
        
        # Список разрешенных нормальных браузеров
        self.allowed_agents = [
            "mozilla", "chrome", "safari", "firefox", "edge", "opera",
            "webkit", "gecko", "applewebkit"
        ]
    
    def is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Проверяет User-Agent на подозрительность"""
        if not user_agent:
            return True
        
        user_agent_lower = user_agent.lower()
        
        # Проверяем на наличие подозрительных строк
        for suspicious in self.suspicious_agents:
            if suspicious in user_agent_lower:
                print(f"🚨 Обнаружен подозрительный User-Agent: {user_agent}")
                return True
        
        # Проверяем, что это нормальный браузер
        is_normal_browser = any(allowed in user_agent_lower 
                              for allowed in self.allowed_agents)
        
        if not is_normal_browser:
            print(f"🚨 Неизвестный User-Agent: {user_agent}")
            return True
        
        return False

# Инициализация систем защиты
rate_limiter = RateLimiter()
user_agent_filter = UserAgentFilter()

# ==================== ПРИЛОЖЕНИЕ FASTAPI ====================

# Создаем таблицы
models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="E-commerce with DDoS Protection")

# Middleware для DDoS защиты
@app.middleware("http")
async def ddos_protection_middleware(request: Request, call_next):
    """Middleware для защиты от DDoS атак"""
    
    # Получаем IP клиента
    client_ip = request.client.host
    
    # Получаем User-Agent
    user_agent = request.headers.get("user-agent", "")
    
    # Логируем запрос для отладки
    print(f"📨 Запрос от {client_ip}: {request.method} {request.url.path} | User-Agent: {user_agent[:50]}...")
    
    # 1. Проверяем User-Agent
    if user_agent_filter.is_suspicious_user_agent(user_agent):
        return Response(
            content="Доступ ограничен",
            status_code=403,
            headers={"X-DDoS-Protection": "Suspicious User-Agent detected"}
        )
    
    # 2. Проверяем лимит запросов (только для не-статических файлов)
    if not request.url.path.startswith("/static/"):
        if rate_limiter.is_rate_limited(client_ip):
            return Response(
                content="Слишком много запросов. Попробуйте позже.",
                status_code=429,
                headers={
                    "X-DDoS-Protection": "Rate limit exceeded",
                    "Retry-After": "300"
                }
            )
    
    # Добавляем заголовки безопасности
    response = await call_next(request)
    
    # Добавляем security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["X-DDoS-Protection"] = "Active"
    
    return response

app.add_middleware(
    SessionMiddleware,
    secret_key="your-secret-key-change-in-production",
    session_cookie="session",
    max_age=3600  # 1 час
)

static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"

static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Подключаем роутеры
app.include_router(auth.router, prefix="/auth")
app.include_router(reports.router, prefix="/reports")
app.include_router(admin.router, prefix="/admin")
app.include_router(payments.router)
app.include_router(checkout.router)

# ==================== БАЗОВЫЕ ФУНКЦИИ ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

# ==================== СИСТЕМА АУТЕНТИФИКАЦИИ ====================

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Получение текущего пользователя из сессии или куки"""
    # Сначала проверяем сессию
    user_id = request.session.get("user_id")
    if user_id: 
        try:
            customer = db.query(models.Customer).filter(models.Customer.id == int(user_id)).first()
            if customer and customer.is_active:
                return customer
        except (ValueError, TypeError):
            pass
    
    # Если в сессии нет, проверяем куки (для обратной совместимости)
    customer_id = request.cookies.get("customer_id")
    if customer_id:
        try:
            customer = db.query(models.Customer).filter(models.Customer.id == int(customer_id)).first()
            if customer and customer.is_active:
                # Мигрируем из куки в сессию
                request.session["user_id"] = customer.id
                request.session["user_role"] = customer.role
                request.session["user_name"] = customer.name
                return customer
        except (ValueError, TypeError):
            pass
    
    return None

def check_admin_access(current_user: models.Customer):
    """Проверка доступа для администратора"""
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав для доступа")

def check_seller_access(current_user: models.Customer):
    """Проверка доступа для продавца"""
    if not current_user or current_user.role not in ["admin", "seller"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав для доступа")

def check_manager_access(current_user: models.Customer):
    """Проверка доступа для менеджера"""
    if not current_user or current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав для доступа")

# ==================== ФУНКЦИИ ДЛЯ ТОВАРОВ ====================

def update_product_popularity(db: Session, product_id: int):
    """Обновляет популярность товара на основе активности"""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product:
        # Расчет популярности на основе различных факторов
        order_count = db.query(models.OrderItem).filter(
            models.OrderItem.product_id == product_id
        ).count()
        
        cart_count = db.query(models.CartItem).filter(
            models.CartItem.product_id == product_id
        ).count()
        
        # Формула расчета популярности
        popularity_score = (
            order_count * 10 +  # Каждая покупка дает 10 баллов
            cart_count * 2 +    # Каждое добавление в корзину дает 2 балла
            product.stock_quantity * 0.1  # Наличие на складе немного влияет
        )
        
        # Ограничиваем максимальную популярность 100 баллами
        popularity_score = min(100, popularity_score)
        
        product.popularity = int(popularity_score)
        db.commit()
        return product.popularity
    return 0

# ==================== ЭНДПОИНТЫ ДЛЯ DDoS ЗАЩИТЫ ====================

@app.get("/admin/security-status")
def get_security_status(
    current_user: models.Customer = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Статус системы защиты (только для админов)"""
    check_admin_access(current_user)
    
    blocked_ips_count = len(rate_limiter.blocked_ips)
    active_ips_count = len(rate_limiter.requests)
    
    # Получаем статистику по заблокированным IP
    blocked_ips = []
    current_time = time.time()
    for ip, block_until in rate_limiter.blocked_ips.items():
        time_remaining = max(0, int(block_until - current_time))
        if time_remaining > 0:
            blocked_ips.append({
                "ip": ip,
                "blocked_until": datetime.fromtimestamp(block_until).strftime("%Y-%m-%d %H:%M:%S"),
                "time_remaining_seconds": time_remaining
            })
    
    # Получаем общую статистику приложения
    total_products = db.query(models.Product).count()
    total_users = db.query(models.Customer).count()
    total_orders = db.query(models.Order).count()
    
    return {
        "application_stats": {
            "total_products": total_products,
            "total_users": total_users,
            "total_orders": total_orders
        },
        "rate_limiting": {
            "max_requests_per_minute": rate_limiter.max_requests_per_minute,
            "block_duration_seconds": rate_limiter.block_duration,
            "active_ips_count": active_ips_count,
            "currently_blocked_count": len(blocked_ips),
            "total_blocked_ips": blocked_ips_count,
            "blocked_ips": blocked_ips
        },
        "user_agent_filtering": {
            "suspicious_patterns_count": len(user_agent_filter.suspicious_agents),
            "allowed_browsers_count": len(user_agent_filter.allowed_agents)
        },
        "protection_status": "ACTIVE"
    }

@app.get("/test/ddos-simulation")
def test_ddos_simulation():
    """Эндпоинт для демонстрации работы защиты (имитирует быстрые запросы)"""
    return {
        "message": "Этот эндпоинт демонстрирует работу защиты от DDoS",
        "protection_active": True,
        "rate_limit": rate_limiter.max_requests_per_minute,
        "block_duration_seconds": rate_limiter.block_duration,
        "test_instructions": "Попробуйте сделать более 60 запросов в минуту к этому эндпоинту",
        "security_headers": {
            "X-DDoS-Protection": "Active",
            "X-RateLimit-Limit": "60 per minute"
        }
    }

@app.get("/test/suspicious-agent")
def test_suspicious_agent():
    """Эндпоинт для тестирования фильтра User-Agent"""
    return {
        "message": "Этот эндпоинт проверяет User-Agent фильтр",
        "note": "Попробуйте сделать запрос с User-Agent содержащим 'bot' или 'scraper'"
    }

# ==================== ОСНОВНЫЕ ЭНДПОИНТЫ ПРИЛОЖЕНИЯ ====================

@app.get("/")
def read_root(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(get_current_user)
):
    categories = db.query(models.Category).all()
    
    # Получаем последние отзывы (только одобренные) с информацией о пользователях и товарах
    recent_reviews = db.query(models.Review).filter(
        models.Review.is_approved == True
    ).options(
        joinedload(models.Review.customer),
        joinedload(models.Review.product)
    ).order_by(models.Review.created_at.desc()).limit(6).all()
    
    # Получаем статистику для отображения
    reviews_count = db.query(models.Review).filter(
        models.Review.is_approved == True
    ).count()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "categories": categories,
        "recent_reviews": recent_reviews,
        "reviews_count": reviews_count,
        "current_user": current_user
    })

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(get_current_user)
):
    if not current_user or current_user.role not in ["admin", "seller", "manager"]:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Недостаточно прав для доступа к этой странице"
        })

    stats = {}
    
    if current_user.role == "admin":
        stats = {
            'products_count': db.query(models.Product).count(),
            'categories_count': db.query(models.Category).count(),
            'orders_count': db.query(models.Order).count(),
            'users_count': db.query(models.Customer).count(),
            'reviews_count': db.query(models.Review).count(),
            'pending_reviews_count': db.query(models.Review).filter(models.Review.is_approved == False).count()
        }
    elif current_user.role == "seller":
        stats = {
            'products_count': db.query(models.Product).count(),
            'categories_count': db.query(models.Category).count(),
            'orders_count': db.query(models.Order).count(),
            'users_count': None,  # Продавцы не видят пользователей
            'reviews_count': db.query(models.Review).count(),
            'pending_reviews_count': db.query(models.Review).filter(models.Review.is_approved == False).count()
        }
    elif current_user.role == "manager":
        stats = {
            'products_count': db.query(models.Product).count(),
            'categories_count': db.query(models.Category).count(),
            'orders_count': db.query(models.Order).count(),
            'users_count': None,  # Менеджеры не видят пользователей
            'reviews_count': db.query(models.Review).count(),
            'pending_reviews_count': db.query(models.Review).filter(models.Review.is_approved == False).count()
        }
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "current_user": current_user,
        **stats  # Распаковываем статистику в контекст
    })

# Маршруты для работы с отзывами
@app.get("/reviews/")
def reviews_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(get_current_user)
):
    """Страница всех отзывов"""
    reviews = db.query(models.Review).filter(
        models.Review.is_approved == True
    ).options(
        joinedload(models.Review.customer),
        joinedload(models.Review.product)
    ).order_by(models.Review.created_at.desc()).all()
    
    return templates.TemplateResponse("reviews.html", {
        "request": request,
        "reviews": reviews,
        "current_user": current_user
    })

@app.post("/reviews/add/{product_id}")
def add_review(
    product_id: int,
    rating: int = Form(...),
    title: str = Form(...),
    comment: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(get_current_user)
):
    """Добавление отзыва к товару"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    
    # Проверяем существование товара
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    # Проверяем, не оставлял ли пользователь уже отзыв на этот товар
    existing_review = db.query(models.Review).filter(
        models.Review.customer_id == current_user.id,
        models.Review.product_id == product_id
    ).first()
    
    if existing_review:
        raise HTTPException(status_code=400, detail="Вы уже оставляли отзыв на этот товар")
    
    # Создаем отзыв
    new_review = models.Review(
        customer_id=current_user.id,
        product_id=product_id,
        rating=rating,
        title=title,
        comment=comment,
        is_approved=True  # В реальном приложении может требовать модерации
    )
    
    db.add(new_review)
    db.commit()
    
    return RedirectResponse(url=f"/products/#product-{product_id}", status_code=303)

@app.get("/cart/", response_class=HTMLResponse)
def cart_page(
    request: Request,
    current_user: models.Customer = Depends(get_current_user)
):
    return templates.TemplateResponse("cart.html", {
        "request": request,
        "current_user": current_user
    })

@app.get("/api/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Получаем отзывы для товара
    reviews = db.query(models.Review).filter(
        models.Review.product_id == product_id,
        models.Review.is_approved == True
    ).all()
    
    # Вычисляем средний рейтинг
    avg_rating = 0
    if reviews:
        avg_rating = sum(review.rating for review in reviews) / len(reviews)
    
    return {
        "id": product.id,
        "name": product.name,
        "price": float(product.price),
        "image_url": product.image_url,
        "stock_quantity": product.stock_quantity,
        "popularity": product.popularity,
        "reviews_count": len(reviews),
        "average_rating": round(avg_rating, 1)
    }

@app.post("/api/products/{product_id}/update-popularity")
def update_popularity(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(get_current_user)
):
    """Обновляет популярность товара (может вызываться при покупке, просмотре и т.д.)"""
    new_popularity = update_product_popularity(db, product_id)
    return {"product_id": product_id, "popularity": new_popularity}

@app.get("/products/", response_class=HTMLResponse)
def products_page(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(get_current_user)
):
    try:
        print(f"DEBUG - Все параметры запроса: {dict(request.query_params)}")
        
        categories = db.query(models.Category).all()
        
        # Получаем параметры фильтрации
        search = request.query_params.get("search", "")
        category_id = request.query_params.get("category_id", "")
        min_price = request.query_params.get("min_price", "")
        max_price = request.query_params.get("max_price", "")
        sort_by = request.query_params.get("sort_by", "")
        
        print(f"DEBUG - Получены параметры: search='{search}', category_id='{category_id}', min_price='{min_price}', max_price='{max_price}', sort_by='{sort_by}'")
        
        # Базовый запрос
        query = db.query(models.Product)
        
        # Применяем фильтры
        if search and search.strip():
            print(f"DEBUG - Применяем фильтр поиска: '{search.strip()}'")
            query = query.filter(models.Product.name.ilike(f"%{search.strip()}%"))
        
        if category_id and category_id.strip():
            try:
                if category_id.strip().isdigit():
                    category_int = int(category_id.strip())
                    print(f"DEBUG - Применяем фильтр категории: {category_int}")
                    query = query.filter(models.Product.category_id == category_int)
            except ValueError as e:
                print(f"DEBUG - Ошибка преобразования category_id: {e}")
        
        if min_price and min_price.strip():
            try:
                min_val = float(min_price.strip())
                if min_val >= 0:
                    print(f"DEBUG - Применяем фильтр минимальной цены: {min_val}")
                    query = query.filter(models.Product.price >= min_val)
            except ValueError as e:
                print(f"DEBUG - Ошибка преобразования min_price: {e}")
        
        if max_price and max_price.strip():
            try:
                max_val = float(max_price.strip())
                if max_val >= 0:
                    print(f"DEBUG - Применяем фильтр максимальной цены: {max_val}")
                    query = query.filter(models.Product.price <= max_val)
            except ValueError as e:
                print(f"DEBUG - Ошибка преобразования max_price: {e}")
        
        # Сортировка
        if sort_by == "name":
            print("DEBUG - Сортировка по имени")
            query = query.order_by(models.Product.name)
        elif sort_by == "price_asc":
            print("DEBUG - Сортировка по цене (возрастание)")
            query = query.order_by(models.Product.price.asc())
        elif sort_by == "price_desc":
            print("DEBUG - Сортировка по цене (убывание)")
            query = query.order_by(models.Product.price.desc())
        elif sort_by == "popularity":
            print("DEBUG - Сортировка по популярности")
            query = query.order_by(models.Product.popularity.desc())
        elif sort_by == "rating":
            print("DEBUG - Сортировка по рейтингу")
            # Здесь нужна более сложная логика для сортировки по рейтингу
            query = query.order_by(models.Product.popularity.desc())
        else:
            print("DEBUG - Сортировка по умолчанию")
            query = query.order_by(models.Product.id)
        
        products = query.all()
        print(f"DEBUG - Найдено товаров: {len(products)}")
        
        # Получаем отзывы для всех товаров
        product_reviews = {}
        for product in products:
            reviews = db.query(models.Review).filter(
                models.Review.product_id == product.id,
                models.Review.is_approved == True
            ).all()
            product_reviews[product.id] = reviews
        
        return templates.TemplateResponse("products.html", {
            "request": request,
            "products": products,
            "categories": categories,
            "product_reviews": product_reviews,
            "current_search": search,
            "current_category_id": category_id,
            "current_min_price": min_price,
            "current_max_price": max_price,
            "current_sort_by": sort_by,
            "current_user": current_user
        })
        
    except Exception as e:
        import logging
        logging.error(f"Error in products page: {e}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "error": str(e)
        })

# ==================== СОЗДАНИЕ ТЕСТОВЫХ ДАННЫХ ====================

def create_test_data():
    """Создание тестовых данных для демонстрации"""
    db = SessionLocal()
    try:
        # Проверяем, есть ли уже данные
        if db.query(models.Customer).count() > 0:
            print("✅ Данные уже существуют в базе")
            return
        
        # Создаем категории
        categories = [
            models.Category(name="Смартфоны", description="Мобильные телефоны и аксессуары", type="product"),
            models.Category(name="Ноутбуки", description="Портативные компьютеры", type="product"),
            models.Category(name="Периферия", description="Компьютерные мыши и клавиатуры", type="product"),
            models.Category(name="Умные технологии", description="Умные часы и умный дом", type="product"),
        ]
        
        for category in categories:
            db.add(category)
        db.commit()
        
        print("✅ Категории созданы")

        # Создаем продукты с разной популярностью
        products = [
            models.Product(
                name="iPhone 15 Pro",
                description="Смартфон Apple с процессором A17 Pro",
                price=99990.00,
                category_id=1,
                stock_quantity=15,
                image_url="/static/images/iphone.png",
                popularity=95
            ),
            models.Product(
                name="Samsung Galaxy S24",
                description="Флагманский смартфон Samsung с AI",
                price=79990.00,
                category_id=1,
                stock_quantity=12,
                image_url="/static/images/samsung.png",
                popularity=88
            ),
            models.Product(
                name="MacBook Air M3",
                description="Ноутбук Apple с чипом M3",
                price=129990.00,
                category_id=2,
                stock_quantity=8,
                image_url="/static/images/macbook.png",
                popularity=92
            ),
            models.Product(
                name="ASUS TUF Gaming F17",
                description="Игровой ноутбук ASUS TUF Gaming F17 FX707ZC4-HX014 с полноразмерной клавиатурой и 17.3-дюймовым экраном ",
                price=75999.00,
                category_id=2,
                stock_quantity=3,
                image_url="/static/images/Asus.png",
                popularity=67
            ),
            models.Product(
                name="Мышь беспроводная Logitech G PRO X SUPERLIGHT 2",
                description="Вы сможете выбрать подходящий режим работы в зависимости от решаемых задач, типа монитора и поверхности под манипулятором.",
                price=2990.00,
                category_id=3,
                stock_quantity=25,
                image_url="/static/images/logitech.png",
                popularity=75
            ),
            models.Product(
                name="Смарт-часы Apple Watch SE 2024 40mm",
                description="Простые способы оставаться на связи.",
                price=19900.00,
                category_id=4,
                stock_quantity=18,
                image_url="/static/images/apple_watch.png",
                popularity=82
            ),
            models.Product(
                name="HUAWEI WATCH GT 6 Pro",
                description="Смарт-часы HUAWEI WATCH GT 6 Pro — это умные носимые устройства.",
                price=26999.00,
                category_id=4,
                stock_quantity=2,
                image_url="/static/images/huawei.png",
                popularity=89
            ),
            models.Product(
                name="Беспроводные наушники Logitech G435 черный",
                description="Радиочастотная гарнитура Logitech G435 LIGHTSPEED поддерживает два способа подключения – Bluetooth и радиоканал.",
                price=5900.00,
                category_id=3,
                stock_quantity=30,
                image_url="/static/images/ears.png",
                popularity=68
            ),
        ]
        
        for product in products:
            db.add(product)
        db.commit()
        
        print("✅ Товары созданы")

        # Создаем пользователей
        admin_user = models.Customer(
            name="Администратор",
            email="admin@example.com",
            hashed_password=hash_password("admin123"),
            role="admin"
        )
        db.add(admin_user)
        
        customer_user = models.Customer(
            name="Иван Покупатель",
            email="customer@example.com",
            hashed_password=hash_password("customer123"),
            role="customer"
        )
        db.add(customer_user)
        
        seller_user = models.Customer(
            name="Продавец",
            email="seller@example.com",
            hashed_password=hash_password("seller123"),
            role="seller"
        )
        db.add(seller_user)

        manager_user = models.Customer(
            name="Менеджер",
            email="manager@example.com",
            hashed_password=hash_password("manager123"),
            role="manager"
        )
        db.add(manager_user)

        # Создаем еще несколько тестовых пользователей для отзывов
        test_customers = [
            models.Customer(
                name="Анна Смирнова",
                email="anna@example.com",
                hashed_password=hash_password("password123"),
                role="customer"
            ),
            models.Customer(
                name="Петр Иванов",
                email="petr@example.com",
                hashed_password=hash_password("password123"),
                role="customer"
            ),
            models.Customer(
                name="Мария Козлова",
                email="maria@example.com",
                hashed_password=hash_password("password123"),
                role="customer"
            ),
            models.Customer(
                name="Сергей Петров",
                email="sergey@example.com",
                hashed_password=hash_password("password123"),
                role="customer"
            )
        ]
        
        for customer in test_customers:
            db.add(customer)
        
        db.commit()
        
        print("✅ Пользователи созданы")

        # Создаем тестовые отзывы
        reviews = [
            models.Review(
                customer_id=customer_user.id,
                product_id=1,  # iPhone 15 Pro
                rating=5,
                title="Отличный смартфон!",
                comment="Пользуюсь уже месяц, все работает идеально. Камера просто супер!",
                is_approved=True
            ),
            models.Review(
                customer_id=test_customers[0].id,
                product_id=1,  # iPhone 15 Pro
                rating=4,
                title="Хороший телефон, но дорогой",
                comment="Качество на высоте, но цена завышена. Батарея держит хорошо.",
                is_approved=True
            ),
            models.Review(
                customer_id=test_customers[1].id,
                product_id=3,  # MacBook Air M3
                rating=5,
                title="Лучший ноутбук для работы",
                comment="Работаю с ним уже 2 месяца - ни разу не завис. Очень доволен покупкой!",
                is_approved=True
            ),
            models.Review(
                customer_id=test_customers[2].id,
                product_id=6,  # Apple Watch SE
                rating=4,
                title="Удобные и функциональные часы",
                comment="Отслеживание активности очень точное. Дизайн стильный.",
                is_approved=True
            ),
            models.Review(
                customer_id=test_customers[3].id,
                product_id=5,  # Наушники Logitech
                rating=5,
                title="Отличный звук!",
                comment="Звук чистый, бас глубокий. Пользуюсь для игр и музыки - все отлично.",
                is_approved=True
            ),
            models.Review(
                customer_id=customer_user.id,
                product_id=2,  # Samsung Galaxy S24
                rating=4,
                title="Хорошая альтернатива Apple",
                comment="AI функции действительно полезны. Камера отличная.",
                is_approved=True
            )
        ]
        
        for review in reviews:
            db.add(review)
        
        db.commit()
        print("✅ Отзывы созданы")
        
        print("\n🎉 Тестовые данные успешно добавлены!")
        print("\n👥 Пользователи:")
        print("📧 Админ - Логин: admin@example.com")
        print("🔑 Админ - Пароль: admin123")
        print("👤 Админ - Роль: admin")
        print("---")
        print("📧 Покупатель - Логин: customer@example.com")
        print("🔑 Покупатель - Пароль: customer123")
        print("👤 Покупатель - Роль: customer")
        print("---")
        print("📧 Продавец - Логин: seller@example.com")
        print("🔑 Продавец - Пароль: seller123")
        print("👤 Продавец - Роль: seller")
        print("---")
        print("📧 Менеджер - Логин: manager@example.com")
        print("🔑 Менеджер - Пароль: manager123")
        print("👤 Менеджер - Роль: manager")
        
        print(f"\n📊 Статистика:")
        print(f"📦 Категории: {len(categories)}")
        print(f"🛍️ Товары: {len(products)}")
        print(f"👥 Пользователи: {len(test_customers) + 4}")
        print(f"⭐ Отзывы: {len(reviews)}")
        
        print(f"\n🏆 Рейтинг популярности товаров:")
        sorted_products = sorted(products, key=lambda x: x.popularity, reverse=True)
        for i, product in enumerate(sorted_products, 1):
            print(f"  {i}. {product.name}: {product.popularity} баллов")
        
        print(f"\n🔐 Права доступа:")
        print("  • Админ: полный доступ ко всему")
        print("  • Продавец: админ-панель, товары, корзина")
        print("  • Менеджер: отчеты, товары, корзина")
        print("  • Покупатель: товары, корзина, отзывы")
        
        print(f"\n🛡️  Система защиты от DDoS активна:")
        print("  • Ограничение запросов: 60/минуту")
        print("  • Фильтрация User-Agent: активна")
        print("  • Мониторинг: /admin/security-status")
        print("  • Тест защиты: /test/ddos-simulation")
        print("  • Тест User-Agent: /test/suspicious-agent")
        
    except Exception as e:
        print(f"❌ Ошибка создания тестовых данных: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()

# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

if __name__ == "__main__":
    import uvicorn
    
    # Создаем тестовые данные
    create_test_data()
    
    print("\n🚀 Запуск приложения с DDoS защитой...")
    print("📍 Доступные эндпоинты для тестирования защиты:")
    print("   • /test/ddos-simulation - тест ограничения запросов")
    print("   • /test/suspicious-agent - тест фильтра User-Agent")
    print("   • /admin/security-status - мониторинг защиты (только для админов)")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
else:
    # Создаем тестовые данные при импорте
    create_test_data()