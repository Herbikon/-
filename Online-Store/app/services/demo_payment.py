import time
import random
from typing import Dict, Any

class DemoPaymentService:
    def __init__(self):
        self.demo_cards = [
            {"number": "5555 5555 5555 4444", "name": "DEMO CARD", "expiry": "12/25"},
            {"number": "4111 1111 1111 1111", "name": "TEST CARD", "expiry": "10/24"}
        ]
    
    def create_payment(self, payment_data: dict) -> Dict[str, Any]:
        """Создание демо-платежа"""
        time.sleep(1)
        
        demo_card = random.choice(self.demo_cards)
        payment_id = f"demo_{int(time.time())}_{random.randint(1000, 9999)}"
        
        return {
            "payment_id": payment_id,
            "status": "pending",
            "confirmation_url": f"/payments/demo/{payment_data['payment_id']}",
            "demo_data": {
                "card_number": demo_card["number"],
                "card_name": demo_card["name"],
                "expiry_date": demo_card["expiry"],
                "cvv": "123"
            }
        }