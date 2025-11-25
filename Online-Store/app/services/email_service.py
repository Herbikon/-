import smtplib
from jinja2 import Template
import os
from datetime import datetime

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@techtown.ru")
    
    def send_receipt(self, to_email: str, payment_data: dict) -> bool:
        try:
            html_content = self._generate_receipt_html(payment_data)
        
        # Всегда сохраняем в файл
            filename = f"receipts/receipt_{payment_data['payment_id']}_{payment_data['order_id']}.html"
            os.makedirs("receipts", exist_ok=True)
        
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
        
            print(f"✅ Чек сохранен: {filename}")
            print(f"📧 Для: {to_email}")
            print(f"📋 Заказ: {payment_data['order_id']}")
            print(f"💰 Сумма: {payment_data['total_amount']} ₽")
        
            return True
        
        except Exception as e:
            print(f"❌ Ошибка сохранения чека: {e}")
            return False
    
    def _generate_receipt_html(self, payment_data: dict) -> str:
        """Генерация красивого HTML чека"""
        # Тот же самый код для генерации HTML, что и выше
        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body { 
                    font-family: 'Arial', sans-serif; 
                    margin: 0; 
                    padding: 20px; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                }
                .receipt-container {
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                    overflow: hidden;
                }
                .header { 
                    background: linear-gradient(135deg, #4e54c8, #8f94fb);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }
                .company { 
                    font-size: 28px; 
                    font-weight: bold; 
                    margin-bottom: 10px;
                }
                .tagline {
                    font-size: 16px;
                    opacity: 0.9;
                }
                .content {
                    padding: 30px;
                }
                .details { 
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                }
                .detail-row {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 8px;
                }
                .detail-label {
                    font-weight: bold;
                    color: #555;
                }
                .items { 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin: 20px 0;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .items th { 
                    background: #4e54c8;
                    color: white;
                    padding: 15px;
                    text-align: left;
                    font-weight: 600;
                }
                .items td { 
                    padding: 12px 15px;
                    border-bottom: 1px solid #eee;
                }
                .items tr:hover {
                    background: #f8f9fa;
                }
                .total { 
                    font-size: 20px; 
                    font-weight: bold; 
                    text-align: right;
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                }
                .footer { 
                    margin-top: 30px; 
                    font-size: 14px; 
                    color: #666; 
                    text-align: center;
                    padding: 20px;
                    border-top: 1px solid #eee;
                }
                .demo-badge {
                    background: #ff6b6b;
                    color: white;
                    padding: 5px 10px;
                    border-radius: 20px;
                    font-size: 12px;
                    margin-left: 10px;
                }
                .thank-you {
                    text-align: center;
                    font-size: 18px;
                    color: #4e54c8;
                    margin: 20px 0;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <div class="receipt-container">
                <div class="header">
                    <div class="company">🛍️ TechTown</div>
                    <div class="tagline">Интернет-магазин электроники</div>
                </div>
                
                <div class="content">
                    <div class="thank-you">Спасибо за покупку! 💝</div>
                    
                    <div class="details">
                        <div class="detail-row">
                            <span class="detail-label">Чек №:</span>
                            <span>{{ payment_id }} <span class="demo-badge">ДЕМО</span></span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Дата:</span>
                            <span>{{ payment_date }}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Заказ №:</span>
                            <span>{{ order_id }}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Email:</span>
                            <span>{{ customer_email }}</span>
                        </div>
                        {% if customer_phone %}
                        <div class="detail-row">
                            <span class="detail-label">Телефон:</span>
                            <span>{{ customer_phone }}</span>
                        </div>
                        {% endif %}
                        <div class="detail-row">
                            <span class="detail-label">Способ оплаты:</span>
                            <span>{{ payment_method }}</span>
                        </div>
                    </div>
                    
                    <table class="items">
                        <thead>
                            <tr>
                                <th>Товар</th>
                                <th>Кол-во</th>
                                <th>Цена</th>
                                <th>Сумма</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in items %}
                            <tr>
                                <td>{{ item.name }}</td>
                                <td>{{ item.quantity }} шт.</td>
                                <td>{{ item.price }} ₽</td>
                                <td>{{ item.quantity * item.price }} ₽</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    
                    <div class="total">
                        💰 Итого к оплате: {{ total_amount }} ₽
                    </div>
                </div>
                
                <div class="footer">
                    <strong>Это демо-версия платежной системы</strong><br>
                    Реальный платеж не проводился<br>
                    Техподдержка: support@techtown.ru<br>
                    Чек сформирован автоматически {{ generation_time }}
                </div>
            </div>
        </body>
        </html>
        """
        
        template = Template(template_str)
        return template.render(
            payment_id=payment_data['payment_id'],
            payment_date=payment_data['payment_date'],
            order_id=payment_data['order_id'],
            customer_email=payment_data['customer_email'],
            customer_phone=payment_data.get('customer_phone', ''),
            payment_method=payment_data.get('payment_method', 'Демо-карта'),
            items=payment_data['items'],
            total_amount=payment_data['total_amount'],
            generation_time=datetime.now().strftime("%d.%m.%Y %H:%M")
        )