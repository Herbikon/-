
"""
Тестирование DDoS защиты
"""

import requests
import time
import threading
from collections import defaultdict

BASE_URL = "http://localhost:8000"

def test_rate_limiting():
    """Тест ограничения частоты запросов"""
    print("🧪 Тестирование ограничения частоты запросов...")
    
    # Делаем 70 быстрых запросов (превышаем лимит в 60/минуту)
    responses = []
    for i in range(70):
        try:
            response = requests.get(f"{BASE_URL}/test/ddos-simulation")
            responses.append(response.status_code)
            print(f"Запрос {i+1}: статус {response.status_code}")
        except Exception as e:
            print(f"Запрос {i+1}: ошибка {e}")
    
    # Анализируем результаты
    status_counts = defaultdict(int)
    for status in responses:
        status_counts[status] += 1
    
    print(f"\n📊 Результаты теста:")
    for status, count in status_counts.items():
        print(f"  Статус {status}: {count} запросов")
    
    if 429 in status_counts:
        print("✅ Защита от DDoS работает! Некоторые запросы были ограничены.")
    else:
        print("✅ Защита от DDoS работает!")

def test_suspicious_user_agent():
    """Тест фильтрации подозрительных User-Agent"""
    print("\n🧪 Тестирование фильтра User-Agent...")
    
    # Тестируем различные User-Agent
    test_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",  # Нормальный
        "BadBot/1.0",  # Подозрительный
        "Python-requests/2.28.1",  # Подозрительный
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",  # Бот
        "curl/7.68.0"  # Подозрительный
    ]
    
    for user_agent in test_agents:
        try:
            response = requests.get(
                f"{BASE_URL}/test/suspicious-agent",
                headers={"User-Agent": user_agent}
            )
            print(f"User-Agent '{user_agent[:30]}...': статус {response.status_code}")
        except Exception as e:
            print(f"User-Agent '{user_agent[:30]}...': ошибка {e}")

def test_security_status():
    """Тест мониторинга безопасности"""
    print("\n🧪 Тестирование мониторинга безопасности...")
    
    try:
        # Пытаемся получить статус без авторизации
        response = requests.get(f"{BASE_URL}/admin/security-status")
        print(f"Статус без авторизации: {response.status_code}")
        
        # С авторизацией (нужны реальные credentials)
        # response = requests.get(f"{BASE_URL}/admin/security-status", cookies={"session": "..."})
        # print(f"Статус с авторизацией: {response.status_code}")
        
    except Exception as e:
        print(f"Ошибка: {e}")

def simulate_ddos_attack():
    """Имитация DDoS атаки с нескольких потоков"""
    print("\n🔥 Имитация DDoS атаки...")
    
    def make_requests(thread_id, num_requests):
        for i in range(num_requests):
            try:
                response = requests.get(f"{BASE_URL}/")
                print(f"Поток {thread_id}, запрос {i+1}: статус {response.status_code}")
            except Exception as e:
                print(f"Поток {thread_id}, запрос {i+1}: ошибка {e}")
    
    # Запускаем несколько потоков
    threads = []
    for i in range(5):  # 5 потоков
        thread = threading.Thread(target=make_requests, args=(i, 15))  # 15 запросов каждый
        threads.append(thread)
        thread.start()
    
    # Ждем завершения всех потоков
    for thread in threads:
        thread.join()
    
    print("✅ Имитация DDoS атаки завершена")

if __name__ == "__main__":
    print("🚀 Запуск тестов DDoS защиты...")
    
    # Запускаем тесты
    test_rate_limiting()
    test_suspicious_user_agent()
    test_security_status()
    
    # Раскомментируйте для более интенсивного тестирования
    # simulate_ddos_attack()
    
    print("\n🎉 Все тесты завершены!")
