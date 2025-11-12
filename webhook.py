#!/usr/bin/env python3
"""
🤖 AGENTE WHATSAPP CON WEBHOOK CAL.COM - VERSIÓN CORREGIDA
=========================================================

Agente de WhatsApp funcional que usa API v2 de Cal.com para generar enlaces dinámicos.

FUNCIONALIDAD:
- Recibe mensajes de WhatsApp
- Procesa solicitud de cita
- Genera enlace de Cal.com dinámicamente via API v2
- Procesa confirmaciones via webhook
- Confirma citas en WhatsApp

Autor: MiniMax Agent
Fecha: 2025-11-12
"""

import os
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración desde .env
WHATSAPP_PHONE = os.getenv('WHATSAPP_PHONE', '+19296025778')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '+14155238886')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
CAL_API_KEY = os.getenv('CAL_API_KEY')
CAL_EVENT_TYPE_ID = os.getenv('CAL_EVENT_TYPE_ID', 'agente-demo')
ACCOUNT_USERNAME = os.getenv('ACCOUNT_USERNAME', 'call-me-please-2tibhe')

# URLs de Cal.com API v2
CAL_API_BASE = "https://api.cal.com/v2"

# Respuestas en múltiples idiomas
RESPONSES = {
    'es': {
        'greeting': "¡Hola! Soy tu agente de citas de WhatsApp. 📅",
        'understanding': "He entendido que quieres agendar una cita.",
        'booking_link': "✨ Puedes agendar tu cita directamente aquí: {}",
        'instructions': "📋 **Instrucciones:**\n1. Haz clic en el enlace de arriba\n2. Selecciona fecha y hora disponibles\n3. Completa el formulario\n4. ¡Recibirás confirmación automática!",
        'confirmation': "✅ ¡Cita confirmada! Recibirás un email de confirmación y luego te confirmaré por WhatsApp.",
        'support': "¿Necesitas ayuda o quieres modificar algo? Solo responde aquí.",
        'booking_received': "¡Perfecto! He recibido tu solicitud de cita. Puedes agendar directamente usando el enlace:",
        'timezone_note': "⏰ Todos los horarios están en tu zona horaria local.",
        'thanks': "¡Gracias por usar nuestro agente de WhatsApp! 😊",
        'error': "❌ Hubo un problema generando el enlace de cita. Por favor intenta de nuevo."
    },
    'en': {
        'greeting': "Hello! I'm your WhatsApp scheduling agent. 📅",
        'understanding': "I understand you want to book an appointment.",
        'booking_link': "✨ You can book your appointment directly here: {}",
        'instructions': "📋 **Instructions:**\n1. Click the link above\n2. Select available date and time\n3. Complete the form\n4. You'll receive automatic confirmation!",
        'confirmation': "✅ Appointment confirmed! You'll receive a confirmation email and I'll confirm via WhatsApp.",
        'support': "Need help or want to modify anything? Just reply here.",
        'booking_received': "Perfect! I've received your booking request. You can schedule directly using the link:",
        'timezone_note': "⏰ All times are in your local timezone.",
        'thanks': "Thanks for using our WhatsApp agent! 😊",
        'error': "❌ There was a problem generating the booking link. Please try again."
    }
}

class WhatsAppWebhookAgent:
    def __init__(self):
        self.app = Flask(__name__)
        self.setup_routes()
        
    def setup_routes(self):
        """Configurar rutas de la aplicación Flask"""
        
        @self.app.route('/webhook/whatsapp', methods=['POST'])
        def whatsapp_webhook():
            """Webhook para recibir mensajes de WhatsApp via Twilio"""
            try:
                # Extraer datos del webhook
                data = request.form
                
                # Información del mensaje
                from_number = data.get('From', '')
                to_number = data.get('To', '')
                message_body = data.get('Body', '').strip()
                message_sid = data.get('MessageSid', '')
                
                logger.info(f"📱 Mensaje recibido de {from_number}: {message_body}")
                
                # Procesar mensaje y responder
                response_text = self.process_message(message_body, from_number)
                
                if response_text:
                    # Enviar respuesta
                    self.send_whatsapp_message(from_number, response_text)
                    logger.info(f"✅ Respuesta enviada a {from_number}")
                
                return jsonify({'status': 'success', 'message': 'Message processed'}), 200
                
            except Exception as e:
                logger.error(f"❌ Error procesando webhook WhatsApp: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/webhook/cal', methods=['POST'])
        def cal_webhook():
            """Webhook para recibir confirmaciones de Cal.com"""
            try:
                # Datos del booking de Cal.com
                booking_data = request.json
                
                logger.info(f"📅 Booking recibido de Cal.com: {json.dumps(booking_data, indent=2)}")
                
                # Extraer información relevante
                booking_id = booking_data.get('id', 'Unknown')
                email = booking_data.get('email', 'Unknown')
                name = booking_data.get('name', 'Unknown')
                start_time = booking_data.get('start_time', 'Unknown')
                event_type = booking_data.get('event_type', {}).get('title', 'Unknown')
                
                # Enviar confirmación por WhatsApp
                self.send_confirmation_whatsapp(email, name, start_time, event_type)
                
                return jsonify({'status': 'success'}), 200
                
            except Exception as e:
                logger.error(f"❌ Error procesando webhook Cal.com: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Endpoint de salud del agente"""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'WhatsApp + Cal.com Webhook Agent (Corregido)',
                'version': '1.1.0-webhook-fixed',
                'config': {
                    'twilio_connected': bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN),
                    'cal_api_configured': bool(CAL_API_KEY),
                    'webhook_urls': {
                        'whatsapp': '/webhook/whatsapp',
                        'cal': '/webhook/cal'
                    }
                }
            })
    
    def get_cal_booking_url(self, event_type_id=None):
        """Generar URL de reserva dinámica usando Cal.com API v2"""
        try:
            if not CAL_API_KEY:
                # Fallback a URL estática si no hay API key
                logger.warning("⚠️ CAL_API_KEY no configurada, usando URL estática")
                return f"https://cal.com/{ACCOUNT_USERNAME}/{event_type_id or CAL_EVENT_TYPE_ID}"
            
            # Usar API v2 de Cal.com para obtener información del evento
            headers = {
                'Authorization': f'Bearer {CAL_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            # Obtener tipos de eventos disponibles
            response = requests.get(
                f"{CAL_API_BASE}/event-types",
                headers=headers
            )
            
            logger.info(f"📡 Respuesta de Cal.com API: {response.status_code}")
            
            if response.status_code == 200:
                event_types = response.json().get('data', [])
                
                # Buscar el tipo de evento específico o usar el primero
                if event_type_id:
                    event_type = next((et for et in event_types if str(et.get('id')) == str(event_type_id)), None)
                else:
                    event_type = event_types[0] if event_types else None
                
                if event_type:
                    booking_url = event_type.get('booking_url', '')
                    if booking_url:
                        logger.info(f"✅ URL de booking generada dinámicamente: {booking_url}")
                        return booking_url
                else:
                    logger.warning(f"⚠️ No se encontró tipo de evento para ID: {event_type_id}")
            else:
                logger.error(f"❌ Error API Cal.com {response.status_code}: {response.text}")
            
            # Fallback si no se puede obtener la URL dinámicamente
            logger.warning("⚠️ No se pudo generar URL dinámica, usando fallback")
            return f"https://cal.com/{ACCOUNT_USERNAME}/{event_type_id or CAL_EVENT_TYPE_ID}"
            
        except Exception as e:
            logger.error(f"❌ Error generando URL de Cal.com: {e}")
            logger.error(f"❌ Detalles del error: {type(e).__name__}: {str(e)}")
            return f"https://cal.com/{ACCOUNT_USERNAME}/{event_type_id or CAL_EVENT_TYPE_ID}"
    
    def detect_language(self, text):
        """Detectar idioma del mensaje"""
        text_lower = text.lower()
        
        # Patrones para detección rápida
        if any(word in text_lower for word in ['hola', 'cita', 'reunión', 'agendar', 'mañana']):
            return 'es'
        elif any(word in text_lower for word in ['hello', 'appointment', 'meeting', 'schedule', 'tomorrow']):
            return 'en'
        else:
            return 'es'  # Default to Spanish
    
    def process_message(self, message_body, from_number):
        """Procesar mensaje y generar respuesta apropiada"""
        try:
            # Detectar idioma
            lang = self.detect_language(message_body)
            responses = RESPONSES.get(lang, RESPONSES['es'])
            
            # Generar URL de reserva dinámicamente
            booking_url = self.get_cal_booking_url()
            booking_link = responses['booking_link'].format(booking_url)
            
            # Keywords para detectar intención de agendar
            scheduling_keywords = [
                'appointment', 'meeting', 'schedule', 'book', 'cita', 'reunión', 
                'agendar', 'ren', 'meeting', 'calendly', 'cal.com'
            ]
            
            # Verificar si es mensaje de inicio de conversación
            if any(keyword in message_body.lower() for keyword in ['hola', 'hello', 'hi', 'start']):
                return f"{responses['greeting']}\n\n{responses['understanding']}\n\n{booking_link}\n\n{responses['instructions']}"
            
            # Verificar intención de agendar
            elif any(keyword in message_body.lower() for keyword in scheduling_keywords):
                return f"{responses['booking_received']}\n\n{booking_link}\n\n{responses['timezone_note']}"
            
            # Respuesta para fechas/horas específicas
            elif any(word in message_body.lower() for word in ['mañana', 'tomorrow', 'demain', 'morgen', 'domani', 'amanhã']):
                return f"{responses['booking_received']}\n\n{booking_link}\n\n{responses['instructions']}"
            
            # Respuesta para otras consultas
            else:
                return f"{responses['greeting']}\n\n{responses['understanding']}\n\n{booking_link}\n\n{responses['support']}"
                
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje: {e}")
            return RESPONSES['es']['error']
    
    def send_whatsapp_message(self, to_number, message):
        """Enviar mensaje de WhatsApp via Twilio"""
        try:
            # Limpiar número - remover prefijo whatsapp si existe
            clean_to_number = to_number.replace('whatsapp:', '').strip()
            
            # URL de la API de Twilio
            url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
            
            # Datos del mensaje
            data = {
                'From': f'whatsapp:{TWILIO_PHONE_NUMBER}',
                'To': f'whatsapp:{clean_to_number}',
                'Body': message
            }
            
            # Headers
            auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            
            # Log de debugging
            logger.info(f"📤 Enviando mensaje a: {clean_to_number}")
            logger.info(f"📤 Desde: {TWILIO_PHONE_NUMBER}")
            
            # Enviar mensaje
            response = requests.post(url, data=data, auth=auth)
            
            if response.status_code == 201:
                logger.info(f"✅ Mensaje enviado exitosamente a {clean_to_number}")
                logger.info(f"📨 SID del mensaje: {response.json().get('sid', 'N/A')}")
            else:
                logger.error(f"❌ Error enviando mensaje a {clean_to_number}: {response.status_code}")
                logger.error(f"📄 Respuesta completa: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Error enviando mensaje de WhatsApp: {e}")
    
    def send_confirmation_whatsapp(self, email, name, start_time, event_type):
        """Enviar confirmación de cita por WhatsApp"""
        try:
            # Formatear fecha y hora para mostrar
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime("%A, %B %d, %Y at %I:%M %p")
            except:
                formatted_time = start_time
            
            # Mensaje de confirmación
            confirmation_message = f"""✅ ¡CITA CONFIRMADA!

📋 **Detalles de tu cita:**
👤 Nombre: {name}
📧 Email: {email}
📅 Fecha y Hora: {formatted_time}
🏷️ Tipo: {event_type}

¡Tu cita ha sido programada exitosamente!

📧 Recibirás recordatorios automáticos por email.
💡 Si necesitas modificar o cancelar, usa el enlace en tu email de confirmación.

¡Gracias por usar nuestro servicio! 😊"""
            
            # Enviar a número del usuario (por ahora al número configurado)
            self.send_whatsapp_message(WHATSAPP_PHONE, confirmation_message)
            
            logger.info(f"📅 Confirmación enviada para {name} - {formatted_time}")
            
        except Exception as e:
            logger.error(f"❌ Error enviando confirmación: {e}")
    
    def run(self, host='0.0.0.0', port=8000):
        """Ejecutar el servidor Flask"""
        logger.info(f"🚀 Agente WhatsApp Webhook CORREGIDO iniciado en http://{host}:{port}")
        logger.info(f"📱 Webhook WhatsApp: http://{host}:{port}/webhook/whatsapp")
        logger.info(f"📅 Webhook Cal.com: http://{host}:{port}/webhook/cal")
        logger.info(f"❤️ Health check: http://{host}:{port}/health")
        
        self.app.run(host=host, port=port, debug=True)

def main():
    """Función principal"""
    print("🤖 INICIANDO AGENTE WHATSAPP WEBHOOK - VERSIÓN CORREGIDA")
    print("=" * 60)
    
    # Verificar credenciales
    required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'WHATSAPP_PHONE', 'TWILIO_PHONE_NUMBER']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Variables de entorno faltantes: {missing_vars}")
        print("📝 Por favor configura tu archivo .env")
        return
    
    # Verificar CAL_API_KEY
    if os.getenv('CAL_API_KEY'):
        print(f"✅ CAL_API_KEY configurada")
    else:
        print(f"⚠️ CAL_API_KEY no configurada, usando URLs estáticas")
    
    # Crear y ejecutar agente
    agent = WhatsAppWebhookAgent()
    agent.run(host='0.0.0.0', port=8000)

if __name__ == '__main__':
    main()