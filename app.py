import os
import requests
import datetime
import dateparser
import re
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from langdetect import detect
from transformers import pipeline
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)

# --- Configuración de Cal.com ---
CAL_API_KEY = os.getenv("CAL_API_KEY").strip()
CAL_USER = "call-me-please-2tibhe"
CAL_EVENT_TYPE = "agente-demo"
CAL_EVENT_TYPE_ID = 3836552
EVENT_DURATION_MINUTES = 30

# --- Configuración de zona horaria ---
# Para mayor precisión, usaremos UTC como base y convertiremos según Cal.com
DEFAULT_TIMEZONE = "America/New_York"

# --- Datos del cliente (estado en memoria) ---
CLIENTS_DATA = {}  # {phone: {name, email, phone}}

# --- Respuestas por idioma ---
RESPONSES = {
    "es": {
        "greeting": "¡Hola! Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?",
        "help": "¿Necesitas ayuda con algo específico? Puedo agendar citas, dar información de precios, ubicación, horarios, etc.",
        "pricing": "Nuestros planes empiezan en $10/mes.",
        "location": "Estamos ubicados en Queens, NY.",
        "hours": "Nuestro horario es de lunes a sábado de 7 AM a 5 PM.",
        "delivery": "Sí, realizamos entregas locales dentro de Queens.",
        "appointment": "¡Perfecto! ¿Podrías decirme tu nombre y email? También me ayudaría conocer tu número de teléfono.",
        "appointment_next_step": "Ahora dime cuándo quieres tu cita (ej: mañana a las 3 PM o hoy a las 4 PM).",
        "appointment_confirmed": "✅ Cita reservada para {date} a las {time}! Revisa tu email.",
        "appointment_error": "Lo siento, hubo un error al reservar. ¿Puedes intentar con otra fecha?",
        "ask_email": "Por favor, proporciona tu email para agendar la cita.",
        "ask_name": "Por favor, proporciona tu nombre completo.",
        "ask_phone": "Por favor, proporciona tu número de teléfono.",
        "ask_time": "¿Cuándo te gustaría tu cita? (ej: mañana a las 3 PM)",
        "default": "Gracias por tu mensaje. ¿En qué más puedo ayudarte?",
        "debug_info": "🕐 Información de debug: Fecha parseada: {parsed}, Fecha objetivo: {target}"
    },
    "en": {
        "greeting": "Hello! I'm your virtual assistant. How can I help you today?",
        "help": "Do you need help with something specific? I can schedule appointments, provide pricing info, location, hours, etc.",
        "pricing": "Our plans start at $10/month.",
        "location": "We are located in Queens, NY.",
        "hours": "We're open Monday to Saturday from 7 AM to 5 PM.",
        "delivery": "Yes, we offer local deliveries within Queens.",
        "appointment": "Great! Could you please tell me your name and email? It would also help to know your phone number.",
        "appointment_next_step": "Now tell me when you'd like your appointment (e.g., tomorrow at 3 PM or today at 4 PM).",
        "appointment_confirmed": "✅ Appointment scheduled for {date} at {time}! Check your email.",
        "appointment_error": "Sorry, there was an error booking your appointment. Could you try another date?",
        "ask_email": "Please provide your email to schedule the appointment.",
        "ask_name": "Please provide your full name.",
        "ask_phone": "Please provide your phone number.",
        "ask_time": "When would you like your appointment? (e.g., tomorrow at 3 PM)",
        "default": "Thank you for your message. How else can I help you?",
        "debug_info": "🕐 Debug info: Parsed date: {parsed}, Target date: {target}"
    },
    "fr": {
        "greeting": "Bonjour ! Je suis votre assistant virtuel. Comment puis-je vous aider aujourd'hui ?",
        "help": "Avez-vous besoin d'aide avec quelque chose de spécifique ? Je peux prendre des rendez-vous, fournir des informations de tarification, localisation, horaires, etc.",
        "pricing": "Nos formules commencent à 10 $/mois.",
        "location": "Nous sommes situés à Queens, NY.",
        "hours": "Nous sommes ouverts du lundi au samedi de 7h à 17h.",
        "delivery": "Oui, nous effectuons des livraisons locales dans Queens.",
        "appointment": "Parfait ! Pourriez-vous me dire votre nom et votre email ? Il serait également utile de connaître votre numéro de téléphone.",
        "appointment_next_step": "Maintenant dites-moi quand vous souhaitez votre rendez-vous (par exemple : demain à 15h ou aujourd'hui à 16h).",
        "appointment_confirmed": "✅ Rendez-vous programmé pour le {date} à {time} ! Vérifiez votre email.",
        "appointment_error": "Désolé, une erreur s'est produite lors de la réservation. Pourriez-vous essayer une autre date ?",
        "ask_email": "Veuillez fournir votre email pour prendre rendez-vous.",
        "ask_name": "Veuillez fournir votre nom complet.",
        "ask_phone": "Veuillez fournir votre numéro de téléphone.",
        "ask_time": "Quand souhaitez-vous votre rendez-vous ? (par exemple : demain à 15h)",
        "default": "Merci pour votre message. En quoi d'autre puis-je vous aider ?",
        "debug_info": "🕐 Info debug: Date parsée: {parsed}, Date cible: {target}"
    },
    "de": {
        "greeting": "Hallo! Ich bin Ihr virtueller Assistent. Wie kann ich Ihnen heute helfen?",
        "help": "Benötigen Sie Hilfe bei etwas Bestimmtem? Ich kann Termine vereinbaren, Preise, Standort, Öffnungszeiten, usw. mitteilen.",
        "pricing": "Unsere Pläne beginnen bei 10 $/Monat.",
        "location": "Wir befinden uns in Queens, NY.",
        "hours": "Wir haben montags bis samstags von 7 bis 17 Uhr geöffnet.",
        "delivery": "Ja, wir liefern lokal innerhalb von Queens.",
        "appointment": "Großartig! Könnten Sie mir bitte Ihren Namen und Ihre E-Mail mitteilen? Es wäre auch hilfreich, Ihre Telefonnummer zu kennen.",
        "appointment_next_step": "Sagen Sie mir jetzt, wann Sie Ihren Termin möchten (z.B.: morgen um 15:00 oder heute um 16:00).",
        "appointment_confirmed": "✅ Termin gebucht für den {date} um {time}! Prüfen Sie Ihre E-Mail.",
        "appointment_error": "Entschuldigung, beim Buchen ist ein Fehler aufgetreten. Können Sie bitte ein anderes Datum versuchen?",
        "ask_email": "Bitte geben Sie Ihre E-Mail für den Termin an.",
        "ask_name": "Bitte geben Sie Ihren vollständigen Namen an.",
        "ask_phone": "Bitte geben Sie Ihre Telefonnummer an.",
        "ask_time": "Wann möchten Sie Ihren Termin? (z.B.: morgen um 15:00)",
        "default": "Danke für Ihre Nachricht. Wie kann ich Ihnen sonst noch helfen?",
        "debug_info": "🕐 Debug-Info: Datum geparst: {parsed}, Zieldatum: {target}"
    },
    "it": {
        "greeting": "Ciao! Sono il tuo assistente virtuale. Come posso aiutarti oggi?",
        "help": "Hai bisogno di aiuto con qualcosa di specifico? Posso prenotare appuntamenti, fornire informazioni sui prezzi, posizione, orari, ecc.",
        "pricing": "I nostri piani partono da $10/mese.",
        "location": "Siamo a Queens, NY.",
        "hours": "Siamo aperti dal lunedì al sabato dalle 7:00 alle 17:00.",
        "delivery": "Sì, effettuiamo consegne locali a Queens.",
        "appointment": "Perfetto! Potresti dirmi il tuo nome e la tua email? Sarebbe utile anche conoscere il tuo numero di telefono.",
        "appointment_next_step": "Ora dimmi quando vuoi il tuo appuntamento (es.: domani alle 15:00 oggi alle 16:00).",
        "appointment_confirmed": "✅ Appuntamento fissato per il {date} alle {time}! Controlla la tua email.",
        "appointment_error": "Spiacenti, si è verificato un errore durante la prenotazione. Potresti provare un'altra data?",
        "ask_email": "Per favore fornisci la tua email per prenotare l'appuntamento.",
        "ask_name": "Per favore fornisci il tuo nome completo.",
        "ask_phone": "Per favore fornisci il tuo numero di telefono.",
        "ask_time": "Quando vuoi il tuo appuntamento? (es.: domani alle 15:00)",
        "default": "Grazie per il tuo messaggio. Come posso aiutarti ancora?",
        "debug_info": "🕐 Info debug: Data analizzata: {parsed}, Data obiettivo: {target}"
    },
    "pt": {
        "greeting": "Olá! Sou seu assistente virtual. Como posso ajudá-lo hoje?",
        "help": "Precisa de ajuda com algo específico? Posso agendar consultas, fornecer informações de preços, localização, horários, etc.",
        "pricing": "Nossos planos começam em US$ 10/mês.",
        "location": "Estamos localizados em Queens, NY.",
        "hours": "Estamos abertos de segunda a sábado das 7h às 18h.",
        "delivery": "Sim, fazemos entregas locais em Queens.",
        "appointment": "Ótimo! Poderia me dizer seu nome e email? Também ajudaria conhecer seu número de telefone.",
        "appointment_next_step": "Agora me diga quando você quer sua consulta (ex.: amanhã às 15h ou hoje às 16h).",
        "appointment_confirmed": "✅ Consulta agendada para {date} às {time}! Verifique seu email.",
        "appointment_error": "Desculpe, ocorreu um erro ao agendar. Você pode tentar outra data?",
        "ask_email": "Por favor forneça seu email para agendar a consulta.",
        "ask_name": "Por favor forneça seu nome completo.",
        "ask_phone": "Por favor forneça seu número de telefone.",
        "ask_time": "Quando você quer sua consulta? (ex.: amanhã às 15h)",
        "default": "Obrigado pela sua mensagem. Como mais posso ajudá-lo?",
        "debug_info": "🕐 Info debug: Data analisada: {parsed}, Data alvo: {target}"
    }
}

print("Cargando modelo de IA...")
intent_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=-1)
print("Modelo listo.")

def is_valid_email(email):
    """Validar formato de email"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None

def is_valid_phone(phone):
    """Validar formato de teléfono básico"""
    phone_pattern = r'^[+\d\s\-\(\)]{10,}$'
    return re.match(phone_pattern, phone) is not None

def extract_email_from_text(text):
    """Extraer email del texto"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(email_pattern, text)
    return matches[0] if matches else None

def extract_phone_from_text(text):
    """Extraer teléfono del texto"""
    phone_patterns = [
        r'\+?1?[\s\-\.]?\(?([0-9]{3})\)?[\s\-\.]?([0-9]{3})[\s\-\.]?([0-9]{4})',  # US/Canada
        r'\+?[\d\s\-\(\)]{10,}',  # General international
    ]
    
    for pattern in phone_patterns:
        matches = re.findall(pattern, text)
        if matches:
            if isinstance(matches[0], tuple):
                # Si es una tupla (3 grupos), unir
                return ''.join(matches[0])
            else:
                # Si es una cadena simple, limpiar
                phone = re.sub(r'[^\d+]', '', str(matches[0]))
                if len(phone) >= 10:
                    return phone
    return None

def extract_name_from_text(text):
    """Extraer nombre del texto"""
    # Remover palabras clave comunes en todos los idiomas
    keywords_to_remove = [
        'mi nombre es', 'me llamo', 'soy', 'my name is', 'i am', 'i\'m',
        'mon nom est', 'je suis', 'mein name ist', 'ich bin', 
        'il mio nome è', 'io sono', 'meu nome é', 'eu sou',
        'mein name ist', 'ich bin', 'ich heiße',
        'o meu nome é', 'eu sou', 'me chamo',
        'mon nom est', 'je m\'appelle'
    ]
    
    name_text = text.lower()
    for keyword in keywords_to_remove:
        name_text = name_text.replace(keyword, '').strip()
    
    # Remover emails, teléfonos y otros patrones
    name_text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', name_text)
    name_text = re.sub(r'\+?[\d\s\-\(\)]{10,}', '', name_text)
    name_text = re.sub(r'[^\w\s]', ' ', name_text)
    
    # Limpiar espacios
    name_text = re.sub(r'\s+', ' ', name_text).strip()
    
    # Si hay palabras, tomar las primeras 2-3 como nombre
    words = name_text.split()
    if len(words) >= 2:
        return ' '.join(words[:2])  # Primer nombre + apellido
    elif len(words) == 1 and len(words[0]) > 2:
        return words[0]
    
    return None

def get_responses_for_lang(lang):
    """Obtener respuestas para un idioma, con fallback a inglés"""
    if lang in RESPONSES:
        return RESPONSES[lang]
    else:
        return RESPONSES["en"]  # Fallback a inglés

def parse_user_date_time(text):
    """
    Parsear fecha y hora del mensaje del usuario de forma mejorada
    """
    # Configuraciones mejoradas para dateparser
    date_settings = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": datetime.datetime.now(),
        "RETURN_AS_TIMEZONE_AWARE": True
    }
    
    # Primera intento con dateparser
    parsed = dateparser.parse(text, settings=date_settings)
    
    # Si dateparser falla, usar heurísticas mejoradas
    if not parsed:
        print(f"🔍 dateparser falló para: {text}")
        
        # Obtener la fecha actual en UTC
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        
        # Detectar palabras clave de tiempo en todos los idiomas
        msg_lower = text.lower()
        target_date = now_utc
        
        # Manejar casos específicos para todos los idiomas
        if any(word in msg_lower for word in [
            "hoy", "today", "aujourd'hui", "oggi", "hoje", "heute", "heute"
        ]):
            # Para "hoy", usar la fecha actual
            target_date = now_utc
        elif any(word in msg_lower for word in [
            "mañana", "tomorrow", "demain", "morgen", "domani", "amanhã"
        ]):
            # Para "mañana", sumar un día
            target_date = now_utc + datetime.timedelta(days=1)
        else:
            # Por defecto, asumir mañana para ser más conservador
            target_date = now_utc + datetime.timedelta(days=1)
        
        # Buscar hora específica
        hour_match = re.search(r'(\d{1,2})\s*(?::\s*(\d{2}))?\s*(am|pm|AM|PM|a\.m\.|p\.m\.?)?', text, re.IGNORECASE)
        
        if hour_match:
            hour = int(hour_match.group(1))
            minute = int(hour_match.group(2)) if hour_match.group(2) else 0
            am_pm = hour_match.group(3)
            
            # Manejar formato 12h vs 24h
            if am_pm:
                am_pm = am_pm.lower().replace('.', '')
                if am_pm in ['pm', 'p.m.', 'p'] and hour != 12:
                    hour += 12
                elif am_pm in ['am', 'a.m.', 'a'] and hour == 12:
                    hour = 0
            
            # Crear datetime con la hora específica
            target_date = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            print(f"🕐 Fecha construida manualmente: {target_date}")
        else:
            # Si no se encuentra hora, usar 2:00 PM por defecto
            target_date = target_date.replace(hour=14, minute=0, second=0, microsecond=0)
            print(f"🕐 Usando hora por defecto (2:00 PM): {target_date}")
        
        parsed = target_date
    
    print(f"✅ Fecha final parseada: {parsed}")
    return parsed

def create_cal_booking(start_time, client_name, client_email, client_phone):
    """Crear reserva en Cal.com"""
    if not CAL_API_KEY:
        return False

    # Usar zona horaria específica para Cal.com
    time_zone = "America/New_York"
    
    # Asegurar que start_time tenga zona horaria
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=datetime.timezone.utc)
    
    # Convertir a la zona horaria de Cal.com
    if start_time.tzinfo == datetime.timezone.utc:
        start_time = start_time.astimezone(datetime.timezone(datetime.timedelta(hours=-5)))  # EST
    
    start_iso = start_time.isoformat()
    end_time = start_time + datetime.timedelta(minutes=EVENT_DURATION_MINUTES)
    end_iso = end_time.isoformat()

    url = "https://api.cal.com/v2/bookings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CAL_API_KEY}"
    }

    payload = {
        "eventTypeId": CAL_EVENT_TYPE_ID,
        "start": start_iso,
        "end": end_iso,
        "timeZone": time_zone,
        "metadata": {},
        "language": "en",
        "responses": {
            "name": client_name,
            "email": client_email,
            "phone": client_phone,
            "notes": f"Reservado desde WhatsApp por {client_name}"
        }
    }

    try:
        print(f"📤 Enviando booking a Cal.com:")
        print(f"   Event Type ID: {CAL_EVENT_TYPE_ID}")
        print(f"   Start: {start_iso}")
        print(f"   End: {end_iso}")
        print(f"   Time Zone: {time_zone}")
        print(f"   Cliente: {client_name} ({client_email})")
        
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"📥 Respuesta de Cal.com: {response.status_code}")
        if response.status_code not in (200, 201):
            print(f"❌ Error: {response.text}")
        
        if response.status_code in (200, 201):
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ Excepción al crear booking: {e}")
        return False

def get_or_create_client(phone):
    """Obtener o crear datos del cliente"""
    if phone not in CLIENTS_DATA:
        CLIENTS_DATA[phone] = {
            'name': None,
            'email': None,
            'phone': phone,
            'appointment_stage': 'collecting_info'  # collecting_info, waiting_time
        }
    return CLIENTS_DATA[phone]

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "").strip()
    
    if not msg or not from_number:
        return str(MessagingResponse().message("Invalid message."))

    print(f"📱 Mensaje recibido de {from_number}: {msg}")

    # Detectar idioma
    try:
        lang = detect(msg)
        print(f"🌍 Idioma detectado: {lang}")
    except:
        lang = "en"
        print("🌍 Idioma no detectado, usando inglés por defecto")

    # Obtener respuestas para el idioma detectado (con fallback a inglés)
    responses = get_responses_for_lang(lang)
    
    # Obtener o crear datos del cliente
    client_data = get_or_create_client(from_number)
    
    resp = MessagingResponse()

    # Detectar intención
    msg_lower = msg.lower()
    appointment_keywords = [
        # Español
        "cita", "reservar", "agendar", "citas", "reservar", "agendar",
        # Inglés
        "appointment", "book", "schedule", "reserve", "schedule", "booking",
        # Francés
        "rendez-vous", "réserver", "prendre", "rendezvous",
        # Alemán
        "termin", "vereinbaren", "buchen", "terminen", "buche",
        # Italiano
        "appuntamento", "prenotare", "fissare", "prenotare", "fissare",
        # Portugués
        "consulta", "agendar", "marcar", "agendar", "marcar"
    ]
    
    is_appointment_request = any(word in msg_lower for word in appointment_keywords)

    # Si es la primera vez o se solicita cita
    if is_appointment_request or client_data['appointment_stage'] == 'collecting_info':
        # Extraer datos del mensaje actual
        extracted_email = extract_email_from_text(msg)
        extracted_phone = extract_phone_from_text(msg)
        extracted_name = extract_name_from_text(msg)
        
        # Actualizar datos del cliente si se extrajeron
        if extracted_email and not client_data['email']:
            client_data['email'] = extracted_email
            print(f"📧 Email extraído: {extracted_email}")
        if extracted_phone and not client_data['phone']:
            client_data['phone'] = extracted_phone
            print(f"📞 Teléfono extraído: {extracted_phone}")
        if extracted_name and not client_data['name']:
            client_data['name'] = extracted_name
            print(f"👤 Nombre extraído: {extracted_name}")
        
        # Verificar qué datos faltan
        missing_info = []
        if not client_data['name']:
            missing_info.append('name')
        if not client_data['email']:
            missing_info.append('email')
        if not client_data['phone']:
            missing_info.append('phone')
        
        if missing_info:
            # Pedir información faltante
            if 'name' in missing_info and 'email' in missing_info and 'phone' in missing_info:
                text = responses['appointment']
            elif 'name' in missing_info:
                text = responses['ask_name']
            elif 'email' in missing_info:
                text = responses['ask_email']
            elif 'phone' in missing_info:
                text = responses['ask_phone']
            
            resp.message(text)
            return str(resp)
        else:
            # Todos los datos están disponibles, ahora pedir fecha/hora
            client_data['appointment_stage'] = 'waiting_time'
            text = responses['appointment_next_step']
            resp.message(text)
            return str(resp)

    # Si ya tenemos todos los datos y esperamos la fecha/hora
    elif client_data['appointment_stage'] == 'waiting_time':
        print(f"🕐 Parseando fecha/hora: {msg}")
        
        # Usar la función mejorada de parsing
        parsed = parse_user_date_time(msg)
        
        if parsed:
            date_str = parsed.strftime("%Y-%m-%d")
            time_str = parsed.strftime("%I:%M %p")
            
            print(f"📅 Fecha objetivo: {date_str}")
            print(f"🕐 Hora objetivo: {time_str}")
            
            # Crear la reserva
            success = create_cal_booking(
                parsed, 
                client_data['name'], 
                client_data['email'], 
                client_data['phone']
            )
            
            if success:
                text = responses['appointment_confirmed'].format(date=date_str, time=time_str)
            else:
                text = responses['appointment_error']
            
            # Reset para la próxima vez
            client_data['appointment_stage'] = 'collecting_info'
            resp.message(text)
            return str(resp)
        else:
            text = responses['ask_time']
            resp.message(text)
            return str(resp)

    # Para otras intenciones
    elif any(word in msg_lower for word in ["precio", "price", "prix", "preis", "preço", "preise"]):
        text = responses['pricing']
    elif any(word in msg_lower for word in ["ubicación", "location", "sitio", "lugar", "standort", "posizione", "localização"]):
        text = responses['location']
    elif any(word in msg_lower for word in ["horario", "hours", "heures", "horário", "stunden", "orari", "horário"]):
        text = responses['hours']
    elif any(word in msg_lower for word in ["entrega", "delivery", "livraison", "entrega", "lieferung", "consegna", "entrega"]):
        text = responses['delivery']
    elif any(word in msg_lower for word in ["ayuda", "help", "aide", "hilfe", "aiuto", "ajuda", "hilfe"]):
        text = responses['help']
    else:
        text = responses['default']
    
    resp.message(text)
    return str(resp)

if __name__ == "__main__":
    print("Iniciando agente de WhatsApp con Cal.com (versión completa multilingüe)...")
    print("🕐 Hora actual del servidor:", datetime.datetime.now())
    print("🌍 Idiomas soportados: ES, EN, FR, DE, IT, PT")
    print("Servidor corriendo en http://0.0.0.0:5000")
    print("Webhook URL: http://0.0.0.0:5000/webhook")
    print("Usa ngrok para exponer el webhook a internet")
    
    app.run(host="0.0.0.0", port=5000, debug=False)