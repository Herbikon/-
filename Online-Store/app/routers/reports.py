from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from database import get_db
import models
import csv
import io
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import func, desc

router = APIRouter()

# Настройка путей для шаблонов
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Зависимость для проверки администратора или менеджера
def require_admin_or_manager(request: Request, db: Session = Depends(get_db)):
    """Требует роль администратора или менеджера"""
    customer_id = request.session.get("user_id")
    if not customer_id:
        raise HTTPException(status_code=403, detail="Требуется авторизация")
    
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer or customer.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    return customer

@router.get("/", response_class=HTMLResponse)
def reports_page(
    request: Request,
    period: int = 7,  # По умолчанию 7 дней
    report_type: str = "all",  # Тип отчета: all, top_products, categories, reviews
    custom_report: str = "",  # Пользовательский тип отчета
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(require_admin_or_manager)
):
    """Страница отчетов - только для администраторов и менеджеров"""
    
    # Ограничиваем период доступными значениями
    if period not in [1, 7, 30, 90]:
        period = 7
    
    # Ограничиваем тип отчета доступными значениями
    if report_type not in ["all", "top_products", "categories", "reviews", "custom"]:
        report_type = "all"
    
    # Если выбран пользовательский отчет, используем его
    if report_type == "custom" and custom_report:
        current_report_type = f"custom_{custom_report}"
    else:
        current_report_type = report_type
    
    # Получаем статистику по отзывам для отображения в интерфейсе
    reviews_stats = get_reviews_statistics(db, period)
    
    return templates.TemplateResponse("reports.html", {
        "request": request,
        "current_user": current_user,
        "current_period": period,
        "current_report_type": current_report_type,
        "current_custom_report": custom_report,
        "categories": db.query(models.Category).all(),
        "reviews_stats": reviews_stats
    })

def get_reviews_statistics(db: Session, period: int):
    """Получение статистики по отзывам за период"""
    # Вычисляем дату начала периода
    start_date = datetime.utcnow() - timedelta(days=period)
    
    # Общее количество отзывов за период
    total_reviews = db.query(models.Review).filter(
        models.Review.created_at >= start_date
    ).count()
    
    # Количество одобренных отзывов
    approved_reviews = db.query(models.Review).filter(
        models.Review.created_at >= start_date,
        models.Review.is_approved == True
    ).count()
    
    # Количество отзывов на модерации
    pending_reviews = db.query(models.Review).filter(
        models.Review.created_at >= start_date,
        models.Review.is_approved == False
    ).count()
    
    # Средний рейтинг
    avg_rating = db.query(func.avg(models.Review.rating)).filter(
        models.Review.created_at >= start_date,
        models.Review.is_approved == True
    ).scalar() or 0
    
    # Распределение по рейтингам
    rating_distribution = db.query(
        models.Review.rating,
        func.count(models.Review.id)
    ).filter(
        models.Review.created_at >= start_date,
        models.Review.is_approved == True
    ).group_by(models.Review.rating).all()
    
    # Топ товаров по количеству отзывов
    top_products_reviews = db.query(
        models.Product.name,
        func.count(models.Review.id).label('review_count'),
        func.avg(models.Review.rating).label('avg_rating')
    ).join(
        models.Review, models.Review.product_id == models.Product.id
    ).filter(
        models.Review.created_at >= start_date,
        models.Review.is_approved == True
    ).group_by(
        models.Product.id, models.Product.name
    ).order_by(
        desc('review_count')
    ).limit(10).all()
    
    # Топ пользователей по оставленным отзывам
    top_reviewers = db.query(
        models.Customer.name,
        models.Customer.email,
        func.count(models.Review.id).label('review_count'),
        func.avg(models.Review.rating).label('avg_rating')
    ).join(
        models.Review, models.Review.customer_id == models.Customer.id
    ).filter(
        models.Review.created_at >= start_date,
        models.Review.is_approved == True
    ).group_by(
        models.Customer.id, models.Customer.name, models.Customer.email
    ).order_by(
        desc('review_count')
    ).limit(10).all()
    
    return {
        'total_reviews': total_reviews,
        'approved_reviews': approved_reviews,
        'pending_reviews': pending_reviews,
        'avg_rating': round(avg_rating, 2),
        'rating_distribution': dict(rating_distribution),
        'top_products_reviews': top_products_reviews,
        'top_reviewers': top_reviewers
    }

def format_currency(amount: int) -> str:
    """Форматирование суммы в рублях с пробелами"""
    return f"{amount:,} ₽".replace(",", " ")

def get_period_text(period: int) -> str:
    """Получить текстовое представление периода"""
    if period == 1:
        return "1 день"
    elif period in [2, 3, 4]:
        return f"{period} дня"
    elif period in [11, 12, 13, 14]:
        return f"{period} дней"
    else:
        return f"{period} дней"

def get_base_products_data():
    """Базовые данные товаров для отчетов"""
    return [
        {"name": "iPhone 15 Pro", "category": "Смартфоны", "price": 99990, "daily_sales": 1},
        {"name": "MacBook Air M3", "category": "Ноутбуки", "price": 129990, "daily_sales": 0},
        {"name": "Samsung Galaxy S24", "category": "Смартфоны", "price": 79990, "daily_sales": 1},
        {"name": "Наушники Logitech", "category": "Периферия", "price": 5900, "daily_sales": 3},
        {"name": "Apple Watch SE", "category": "Умные технологии", "price": 19900, "daily_sales": 2},
        {"name": "Мышь Logitech", "category": "Периферия", "price": 2990, "daily_sales": 2},
        {"name": "Xiaomi Redmi Note 13", "category": "Смартфоны", "price": 24990, "daily_sales": 1}
    ]

def generate_reviews_report(writer, period: int, current_user, db: Session):
    """Генерация отчета по отзывам"""
    # Получаем статистику по отзывам
    stats = get_reviews_statistics(db, period)
    
    writer.writerow(["ОТЧЕТ ПО ОТЗЫВАМ ПОКУПАТЕЛЕЙ"])
    writer.writerow([f"Период: {get_period_text(period)}"])
    writer.writerow([f"Сгенерирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}"])
    writer.writerow(["Пользователь:", current_user.email])
    writer.writerow(["Роль:", current_user.role])
    writer.writerow([])
    
    # Общая статистика
    writer.writerow(["ОБЩАЯ СТАТИСТИКА ОТЗЫВОВ"])
    writer.writerow(["Показатель", "Значение"])
    writer.writerow(["Всего отзывов", str(stats['total_reviews'])])
    writer.writerow(["Одобрено отзывов", str(stats['approved_reviews'])])
    writer.writerow(["На модерации", str(stats['pending_reviews'])])
    writer.writerow(["Средний рейтинг", f"{stats['avg_rating']:.2f}"])
    writer.writerow(["Процент одобрения", f"{(stats['approved_reviews'] / stats['total_reviews'] * 100) if stats['total_reviews'] > 0 else 0:.1f}%"])
    writer.writerow([])
    
    # Распределение по рейтингам
    writer.writerow(["РАСПРЕДЕЛЕНИЕ ПО РЕЙТИНГАМ"])
    writer.writerow(["Рейтинг", "Количество", "Доля"])
    
    total_approved = stats['approved_reviews']
    for rating in range(1, 6):
        count = stats['rating_distribution'].get(rating, 0)
        percentage = (count / total_approved * 100) if total_approved > 0 else 0
        writer.writerow([
            "★" * rating,
            str(count),
            f"{percentage:.1f}%"
        ])
    writer.writerow([])
    
    # Топ товаров по отзывам
    writer.writerow(["ТОП ТОВАРОВ ПО КОЛИЧЕСТВУ ОТЗЫВОВ"])
    writer.writerow(["№", "Товар", "Отзывов", "Средний рейтинг"])
    
    for i, product in enumerate(stats['top_products_reviews'], 1):
        writer.writerow([
            str(i),
            product.name,
            str(product.review_count),
            f"{product.avg_rating:.2f}"
        ])
    writer.writerow([])
    
    # Топ пользователей по отзывам
    writer.writerow(["ТОП ПОКУПАТЕЛЕЙ ПО ОТЗЫВАМ"])
    writer.writerow(["№", "Покупатель", "Email", "Отзывов", "Средний рейтинг"])
    
    for i, reviewer in enumerate(stats['top_reviewers'], 1):
        writer.writerow([
            str(i),
            reviewer.name,
            reviewer.email,
            str(reviewer.review_count),
            f"{reviewer.avg_rating:.2f}"
        ])
    writer.writerow([])
    
    # Детальная информация по отзывам
    writer.writerow(["ПОСЛЕДНИЕ ОТЗЫВЫ"])
    writer.writerow(["Дата", "Покупатель", "Товар", "Рейтинг", "Статус", "Заголовок"])
    
    # Получаем последние отзывы
    start_date = datetime.utcnow() - timedelta(days=period)
    recent_reviews = db.query(
        models.Review,
        models.Customer.name,
        models.Product.name
    ).join(
        models.Customer, models.Review.customer_id == models.Customer.id
    ).join(
        models.Product, models.Review.product_id == models.Product.id
    ).filter(
        models.Review.created_at >= start_date
    ).order_by(
        models.Review.created_at.desc()
    ).limit(50).all()
    
    for review, customer_name, product_name in recent_reviews:
        status = "Одобрен" if review.is_approved else "На модерации"
        writer.writerow([
            review.created_at.strftime('%d.%m.%Y'),
            customer_name,
            product_name,
            "★" * review.rating,
            status,
            review.title or "Без заголовка"
        ])

def generate_custom_report(writer, period: int, current_user, base_products, report_type: str, db: Session = None):
    """Генерация пользовательского отчета"""
    multiplier = period
    
    writer.writerow([f"ПОЛЬЗОВАТЕЛЬСКИЙ ОТЧЕТ: {report_type.upper()}"])
    writer.writerow([f"Период: {get_period_text(period)}"])
    writer.writerow([f"Сгенерирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}"])
    writer.writerow(["Пользователь:", current_user.email])
    writer.writerow(["Роль:", current_user.role])
    writer.writerow([])
    
    # В зависимости от типа пользовательского отчета генерируем разный контент
    if "отзыв" in report_type.lower() or "review" in report_type.lower():
        # Отчет по отзывам
        generate_reviews_report(writer, period, current_user, db)
    
    elif "топ" in report_type.lower() or "top" in report_type.lower():
        # Топ товаров
        writer.writerow(["ТОП ПРОДАВАЕМЫХ ТОВАРОВ"])
        writer.writerow(["№", "Товар", "Категория", "Цена", "Продано", "Выручка"])
        
        products_data = []
        for product in base_products:
            sold_count = product["daily_sales"] * multiplier
            revenue = product["price"] * sold_count
            products_data.append({
                "name": product["name"],
                "category": product["category"],
                "price": product["price"],
                "sold_count": sold_count,
                "revenue": revenue
            })
        
        products_data.sort(key=lambda x: x["revenue"], reverse=True)
        
        for i, product in enumerate(products_data, 1):
            writer.writerow([
                str(i),
                product["name"],
                product["category"],
                format_currency(product["price"]),
                str(product["sold_count"]),
                format_currency(product["revenue"])
            ])
    
    elif "катего" in report_type.lower() or "categor" in report_type.lower():
        # По категориям
        writer.writerow(["СТАТИСТИКА ПО КАТЕГОРИЯМ"])
        writer.writerow(["№", "Категория", "Товаров", "Продано", "Выручка", "Доля"])
        
        categories_stats = {}
        for product in base_products:
            category = product["category"]
            if category not in categories_stats:
                categories_stats[category] = {
                    "product_count": 0,
                    "total_sold": 0,
                    "total_revenue": 0
                }
            
            categories_stats[category]["product_count"] += 1
            categories_stats[category]["total_sold"] += product["daily_sales"] * multiplier
            categories_stats[category]["total_revenue"] += product["price"] * product["daily_sales"] * multiplier
        
        total_revenue_all = sum(stats["total_revenue"] for stats in categories_stats.values())
        
        categories_data = []
        for category, stats in categories_stats.items():
            revenue_share = (stats["total_revenue"] / total_revenue_all * 100) if total_revenue_all > 0 else 0
            categories_data.append({
                "category": category,
                "product_count": stats["product_count"],
                "total_sold": stats["total_sold"],
                "total_revenue": stats["total_revenue"],
                "revenue_share": revenue_share
            })
        
        categories_data.sort(key=lambda x: x["total_revenue"], reverse=True)
        
        for i, category in enumerate(categories_data, 1):
            writer.writerow([
                str(i),
                category["category"],
                str(category["product_count"]),
                str(category["total_sold"]),
                format_currency(category["total_revenue"]),
                f"{category['revenue_share']:.1f}%"
            ])
    
    else:
        # Общий пользовательский отчет
        writer.writerow(["ОБЩАЯ СТАТИСТИКА"])
        writer.writerow(["Показатель", "Значение"])
        
        total_items = sum(product["daily_sales"] * multiplier for product in base_products)
        total_revenue = sum(product["price"] * product["daily_sales"] * multiplier for product in base_products)
        total_orders = round(total_items / 2.7)
        avg_order = total_revenue / total_orders if total_orders > 0 else 0
        
        writer.writerow(["Общая выручка", format_currency(total_revenue)])
        writer.writerow(["Всего заказов", str(total_orders)])
        writer.writerow(["Товаров продано", str(total_items)])
        writer.writerow(["Средний чек", format_currency(int(avg_order))])
        writer.writerow(["Количество товаров", str(len(base_products))])
        writer.writerow(["Количество категорий", str(len(set(p["category"] for p in base_products)))])

def generate_top_products_report(writer, period: int, current_user, base_products):
    """Генерация отчета по топ продаваемым товарам"""
    multiplier = period
    
    writer.writerow(["ОТЧЕТ ПО ТОП ПРОДАЖАМ"])
    writer.writerow([f"Период: {get_period_text(period)}"])
    writer.writerow([f"Сгенерирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}"])
    writer.writerow(["Пользователь:", current_user.email])
    writer.writerow(["Роль:", current_user.role])
    writer.writerow([])
    
    writer.writerow(["ТОП-10 ПРОДАВАЕМЫХ ТОВАРОВ"])
    writer.writerow(["№", "Товар", "Категория", "Цена", "Продано", "Выручка"])
    
    products_data = []
    for product in base_products:
        sold_count = product["daily_sales"] * multiplier
        revenue = product["price"] * sold_count
        products_data.append({
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "sold_count": sold_count,
            "revenue": revenue
        })
    
    products_data.sort(key=lambda x: x["revenue"], reverse=True)
    
    for i, product in enumerate(products_data[:10], 1):
        writer.writerow([
            str(i),
            product["name"],
            product["category"],
            format_currency(product["price"]),
            str(product["sold_count"]),
            format_currency(product["revenue"])
        ])

def generate_categories_report(writer, period: int, current_user, base_products):
    """Генерация отчета по категориям"""
    multiplier = period
    
    writer.writerow(["ОТЧЕТ ПО КАТЕГОРИЯМ"])
    writer.writerow([f"Период: {get_period_text(period)}"])
    writer.writerow([f"Сгенерирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}"])
    writer.writerow(["Пользователь:", current_user.email])
    writer.writerow(["Роль:", current_user.role])
    writer.writerow([])
    
    writer.writerow(["СТАТИСТИКА ПО КАТЕГОРИЯМ"])
    writer.writerow(["№", "Категория", "Товаров", "Продано", "Выручка", "Доля"])
    
    categories_stats = {}
    for product in base_products:
        category = product["category"]
        if category not in categories_stats:
            categories_stats[category] = {
                "product_count": 0,
                "total_sold": 0,
                "total_revenue": 0
            }
        
        categories_stats[category]["product_count"] += 1
        categories_stats[category]["total_sold"] += product["daily_sales"] * multiplier
        categories_stats[category]["total_revenue"] += product["price"] * product["daily_sales"] * multiplier
    
    total_revenue_all = sum(stats["total_revenue"] for stats in categories_stats.values())
    
    categories_data = []
    for category, stats in categories_stats.items():
        revenue_share = (stats["total_revenue"] / total_revenue_all * 100) if total_revenue_all > 0 else 0
        categories_data.append({
            "category": category,
            "product_count": stats["product_count"],
            "total_sold": stats["total_sold"],
            "total_revenue": stats["total_revenue"],
            "revenue_share": revenue_share
        })
    
    categories_data.sort(key=lambda x: x["total_revenue"], reverse=True)
    
    for i, category in enumerate(categories_data, 1):
        writer.writerow([
            str(i),
            category["category"],
            str(category["product_count"]),
            str(category["total_sold"]),
            format_currency(category["total_revenue"]),
            f"{category['revenue_share']:.1f}%"
        ])

def generate_full_report(writer, period: int, current_user, base_products):
    """Генерация полного отчета"""
    multiplier = period
    
    writer.writerow(["ПОЛНЫЙ ОТЧЕТ О ПРОДАЖАХ"])
    writer.writerow([f"Период: {get_period_text(period)}"])
    writer.writerow([f"Сгенерирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}"])
    writer.writerow(["Пользователь:", current_user.email])
    writer.writerow(["Роль:", current_user.role])
    writer.writerow([])
    
    # Общая статистика
    writer.writerow(["ОБЩАЯ СТАТИСТИКА"])
    writer.writerow(["Показатель", "Значение"])
    
    total_items = sum(product["daily_sales"] * multiplier for product in base_products)
    total_revenue = sum(product["price"] * product["daily_sales"] * multiplier for product in base_products)
    total_orders = round(total_items / 2.7)
    avg_order = total_revenue / total_orders if total_orders > 0 else 0
    
    writer.writerow(["Общая выручка", format_currency(total_revenue)])
    writer.writerow(["Всего заказов", str(total_orders)])
    writer.writerow(["Товаров продано", str(total_items)])
    writer.writerow(["Средний чек", format_currency(int(avg_order))])
    writer.writerow([])
    
    # Топ товаров
    writer.writerow(["ТОП-5 ПРОДАВАЕМЫХ ТОВАРОВ"])
    writer.writerow(["№", "Товар", "Категория", "Цена", "Продано", "Выручка"])
    
    products_data = []
    for product in base_products:
        sold_count = product["daily_sales"] * multiplier
        revenue = product["price"] * sold_count
        products_data.append({
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "sold_count": sold_count,
            "revenue": revenue
        })
    
    products_data.sort(key=lambda x: x["revenue"], reverse=True)
    
    for i, product in enumerate(products_data[:5], 1):
        writer.writerow([
            str(i),
            product["name"],
            product["category"],
            format_currency(product["price"]),
            str(product["sold_count"]),
            format_currency(product["revenue"])
        ])
    
    writer.writerow([])
    
    # Статистика по категориям
    writer.writerow(["СТАТИСТИКА ПО КАТЕГОРИЯМ"])
    writer.writerow(["Категория", "Товаров", "Продано", "Выручка", "Доля"])
    
    categories_stats = {}
    for product in base_products:
        category = product["category"]
        if category not in categories_stats:
            categories_stats[category] = {
                "product_count": 0,
                "total_sold": 0,
                "total_revenue": 0
            }
        
        categories_stats[category]["product_count"] += 1
        categories_stats[category]["total_sold"] += product["daily_sales"] * multiplier
        categories_stats[category]["total_revenue"] += product["price"] * product["daily_sales"] * multiplier
    
    total_revenue_all = sum(stats["total_revenue"] for stats in categories_stats.values())
    
    for category, stats in categories_stats.items():
        revenue_share = (stats["total_revenue"] / total_revenue_all * 100) if total_revenue_all > 0 else 0
        writer.writerow([
            category,
            str(stats["product_count"]),
            str(stats["total_sold"]),
            format_currency(stats["total_revenue"]),
            f"{revenue_share:.1f}%"
        ])

@router.get("/export/")
def export_reports(
    period: int = 7,
    report_type: str = "all",  # all, top_products, categories, reviews, custom
    custom_report: str = "",
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(require_admin_or_manager)
):
    """Экспорт отчета в CSV с выбором типа отчета"""
    
    # Ограничиваем период доступными значениями
    if period not in [1, 7, 30, 90]:
        period = 7
    
    # Ограничиваем тип отчета доступными значениями
    if report_type not in ["all", "top_products", "categories", "reviews", "custom"]:
        report_type = "all"
    
    # Базовые данные товаров
    base_products = get_base_products_data()
    
    # Создаем CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer = docx.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer = pdf.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # Генерация отчета в зависимости от типа
    if report_type == "top_products":
        generate_top_products_report(writer, period, current_user, base_products)
        filename = f"techtown_top_products_{period}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    elif report_type == "categories":
        generate_categories_report(writer, period, current_user, base_products)
        filename = f"techtown_categories_{period}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    elif report_type == "reviews":
        generate_reviews_report(writer, period, current_user, db)
        filename = f"techtown_reviews_{period}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    elif report_type == "custom" and custom_report:
        generate_custom_report(writer, period, current_user, base_products, custom_report, db)
        # Создаем безопасное имя файла только с латинскими символами
        safe_name = "".join(c for c in custom_report if c.isalnum() or c in (' ', '-', '_')).rstrip()
        # Заменяем русские символы на английские аналоги или удаляем их
        safe_name = safe_name.replace(' ', '_').replace('-', '_')
        # Удаляем все не-ASCII символы
        safe_name = safe_name.encode('ascii', 'ignore').decode('ascii')
        if not safe_name:
            safe_name = "custom_report"
        filename = f"techtown_{safe_name}_{period}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    else:  # all
        generate_full_report(writer, period, current_user, base_products)
        filename = f"techtown_full_report_{period}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    
    # Подготовка ответа
    output.seek(0)
    csv_content = output.getvalue()
    docx_content = output.getvalue()
    pdf_content = output.getvalue()
    
    return Response(
        content=csv_content.encode('utf-8-sig'),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
    return Response(
        content=docx_content.encode('utf-8-sig'),
        media_type="text/docx; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
    return Response(
        content=pdf_content.encode('utf-8-sig'),
        media_type="text/pdf; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Дополнительные маршруты для управления отзывами
@router.get("/reviews/moderation")
def reviews_moderation_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(require_admin_or_manager)
):
    """Страница модерации отзывов"""
    
    # Получаем отзывы на модерации
    pending_reviews = db.query(
        models.Review,
        models.Customer.name,
        models.Product.name
    ).join(
        models.Customer, models.Review.customer_id == models.Customer.id
    ).join(
        models.Product, models.Review.product_id == models.Product.id
    ).filter(
        models.Review.is_approved == False
    ).order_by(
        models.Review.created_at.desc()
    ).all()
    
    # Получаем последние одобренные отзывы
    approved_reviews = db.query(
        models.Review,
        models.Customer.name,
        models.Product.name
    ).join(
        models.Customer, models.Review.customer_id == models.Customer.id
    ).join(
        models.Product, models.Review.product_id == models.Product.id
    ).filter(
        models.Review.is_approved == True
    ).order_by(
        models.Review.created_at.desc()
    ).limit(20).all()
    
    return templates.TemplateResponse("reviews_moderation.html", {
        "request": request,
        "current_user": current_user,
        "pending_reviews": pending_reviews,
        "approved_reviews": approved_reviews
    })

@router.post("/reviews/{review_id}/approve")
def approve_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(require_admin_or_manager)
):
    """Одобрение отзыва"""
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    
    review.is_approved = True
    db.commit()
    
    return {"message": "Отзыв одобрен"}

@router.post("/reviews/{review_id}/reject")
def reject_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: models.Customer = Depends(require_admin_or_manager)
):
    """Отклонение отзыва"""
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    
    db.delete(review)
    db.commit()
    
    return {"message": "Отзыв отклонен и удален"}