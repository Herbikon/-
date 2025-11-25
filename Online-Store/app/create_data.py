import os
import sys
import bcrypt
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models


def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_sample_data():
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
            models.Category(name="Переферия", description="Компьютерные мыши и клавиатуры", type="product"),
            models.Category(name="Умные технологии", description="Умные часы и умный дом", type="product"),
        ]
        
        for category in categories:
            db.add(category)
        db.commit()
        
        print("✅ Категории созданы")

        # Создаем продукты
        products = [
            models.Product(
                name="iPhone 15 Pro",
                description="Смартфон Apple с процессором A17 Pro",
                price=99990.00,
                category_id=1,
                stock_quantity=1,
                image_url="/static/images/iphone.png"
            ),
            models.Product(
                name="Samsung Galaxy S24",
                description="Флагманский смартфон Samsung с AI",
                price=79990.00,
                category_id=1,
                stock_quantity=2,
                image_url="/static/images/samsung.png"
            ),
            models.Product(
                name="MacBook Air M3",
                description="Ноутбук Apple с чипом M3",
                price=129990.00,
                category_id=2,
                stock_quantity=3,
                image_url="/static/images/macbook.png"
            ),
            models.Product(
                name="Мышь беспроводная Logitech G PRO X SUPERLIGHT 2",
                description="Вы сможете выбрать подходящий режим работы в зависимости от решаемых задач, типа монитора и поверхности под манипулятором.",
                price=2990.00,
                category_id=3,
                stock_quantity=4,
                image_url="/static/images/logitech.png"
            ),
            models.Product(
                name="Смарт-часы Apple Watch SE 2024 40mm",
                description="Простые способы оставаться на связи.",
                price=19900.00,
                category_id=4,
                stock_quantity=5,
                image_url="/static/images/apple_watch.png"
            ),
            models.Product(
                name="Беспроводные наушники Logitech G435 черный",
                description="Радиочастотная гарнитура Logitech G435 LIGHTSPEED поддерживает два способа подключения – Bluetooth и радиоканал.",
                price=5900.00,
                category_id=3,
                stock_quantity=5,
                image_url="/static/images/ears.png"
            ),
        ]
        
        for product in products:
            db.add(product)
        db.commit()
        
        print("✅ Товары созданы")

        # Создаем администратора
        admin_user = models.Customer(
            name="Администратор",
            email="admin@example.com",
            hashed_password=hash_password("admin123"),
            role="admin"  # Используем "admin" вместо "director" для совместимости
        )
        db.add(admin_user)
        
        # Создаем обычного пользователя
        customer_user = models.Customer(
            name="Иван Покупатель",
            email="customer@example.com",
            hashed_password=hash_password("customer123"),
            role="customer"
        )
        db.add(customer_user)
        
        db.commit()
        
        print("\n🎉 Тестовые данные успешно добавлены!")
        print("\n👥 Пользователи:")
        print("📧 Админ - Логин: admin@example.com")
        print("🔑 Админ - Пароль: admin123")
        print("👤 Админ - Роль: admin")
        print("---")
        print("📧 Покупатель - Логин: customer@example.com")
        print("🔑 Покупатель - Пароль: customer123")
        print("👤 Покупатель - Роль: customer")
        
        print(f"\n📊 Статистика:")
        print(f"📦 Категории: {len(categories)}")
        print(f"🛍️ Товары: {len(products)}")
        print(f"👥 Пользователи: 2")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    # Создаем таблицы если их нет
    print("🔄 Создание таблиц в базе данных...")
    models.Base.metadata.create_all(bind=engine)
    create_sample_data()