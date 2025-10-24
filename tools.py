import logging
from livekit.agents import function_tool, RunContext
import requests
import os
import smtplib
from email.mime.multipart import MIMEMultipart  
from email.mime.text import MIMEText
from typing import Optional
import subprocess
from datetime import datetime, timedelta
import asyncio
import webbrowser
from urllib.parse import quote_plus
import pickle
import pytz

# --- Google Calendar OAuth Imports ---
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# --- Locate JSON Credentials ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "client_secret.json")

# ----------------------------------------------------------
# OPEN APPLICATIONS
# ----------------------------------------------------------
@function_tool()
async def open_app(context: RunContext, app_name: str) -> str:
    """Open a Windows application by name."""
    apps = {
        "notepad": r"C:\Windows\System32\notepad.exe",
        "calculator": r"C:\Windows\System32\calc.exe",
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "vscode": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
        "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    }

    for key, path in apps.items():
        apps[key] = os.path.expandvars(path)

    path = apps.get(app_name.lower())
    if not path:
        return f"App '{app_name}' not recognized or not configured."

    try:
        subprocess.Popen([path])
        logging.info(f"App '{app_name}' opened successfully")
        return f"{app_name.title()} opened successfully!"
    except Exception as e:
        logging.error(f"Failed to open {app_name}: {e}")
        return f"Failed to open {app_name}: {e}"

# ----------------------------------------------------------
# PERSONALIZED GREETING
# ----------------------------------------------------------
@function_tool()
async def greet_user(context: RunContext, user_name: str = "User") -> str:
    """Return a personalized greeting."""
    now = datetime.now()
    greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
    return f"{greeting}, {user_name}! How can I assist you today?"

# ----------------------------------------------------------
# WEB SEARCH
# ----------------------------------------------------------
@function_tool()
async def search_web(context: RunContext, query: str) -> str:
    """Search the web using Google Chrome browser."""
    try:
        encoded_query = quote_plus(query)
        search_url = f"https://www.google.com/search?q={encoded_query}"

        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]

        chrome_path = next((p for p in chrome_paths if os.path.exists(p)), None)
        if chrome_path:
            webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
            webbrowser.get('chrome').open_new_tab(search_url)
            logging.info(f"Opened Chrome search for: {query}")
            return f"Searching the web for '{query}' using Chrome..."
        else:
            webbrowser.open(search_url)
            logging.warning("Chrome not found — using default browser instead.")
            return f"Chrome not found. Searching the web for '{query}' using default browser."

    except Exception as e:
        logging.error(f"Error opening Chrome for '{query}': {e}")
        return f"Failed to search the web: {e}"

# ----------------------------------------------------------
# GET WEATHER
# ----------------------------------------------------------
@function_tool()
async def get_weather(context: RunContext, city: str = "Manila") -> str:
    """Get the current weather using wttr.in JSON API."""
    try:
        url = f"https://wttr.in/{city}?format=j1"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            logging.error(f"Weather API error {response.status_code}: {response.text}")
            return f"Could not retrieve weather for {city}."

        data = response.json()
        current = data["current_condition"][0]
        
        weather_desc = current["weatherDesc"][0]["value"]
        temp_c = current["temp_C"]
        feels_like = current["FeelsLikeC"]
        humidity = current["humidity"]
        wind_kph = current["windspeedKmph"]

        report = (
            f"The current weather in {city} is {weather_desc}. "
            f"Temperature: {temp_c}°C (feels like {feels_like}°C). "
            f"Humidity: {humidity}%. Wind speed: {wind_kph} km/h."
        )

        logging.info(f"Weather report for {city}: {report}")
        return report

    except Exception as e:
        logging.error(f"Error retrieving weather for {city}: {e}")
        return f"An error occurred while retrieving weather for {city}: {str(e)}"

# ----------------------------------------------------------
# SEND EMAIL
# ----------------------------------------------------------
@function_tool()    
async def send_email(context: RunContext, to_email: str, subject: str, message: str, cc_email: Optional[str] = None) -> str:
    """Send an email through Gmail."""
    try:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        
        if not gmail_user or not gmail_password:
            logging.error("Gmail credentials not found")
            return "Email sending failed: Gmail credentials not configured."
        
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        recipients = [to_email]
        if cc_email:
            msg['Cc'] = cc_email
            recipients.append(cc_email)
        
        msg.attach(MIMEText(message, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipients, msg.as_string())
        server.quit()
        
        logging.info(f"Email sent successfully to {to_email}")
        return f"Email sent successfully to {to_email}"
        
    except smtplib.SMTPAuthenticationError:
        logging.error("Gmail authentication failed")
        return "Email sending failed: Authentication error. Check Gmail credentials."
    except smtplib.SMTPException as e:
        logging.error(f"SMTP error: {e}")
        return f"Email sending failed: SMTP error - {str(e)}"
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        return f"An error occurred while sending email: {str(e)}"

# ----------------------------------------------------------
# GOOGLE CALENDAR TASK SCHEDULING
# ----------------------------------------------------------
@function_tool()
async def schedule_task_with_google_calendar(
    context: RunContext,  
    title: str,
    description: str,
    minutes_from_now: int
) -> str:
    """Schedule a task in Google Calendar using OAuth."""
    try:
        SCOPES = ["https://www.googleapis.com/auth/calendar"]
        token_path = os.path.join(BASE_DIR, "token.pickle")
        creds = None

        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, "wb") as token:
                    pickle.dump(creds, token)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, "wb") as token:
                    pickle.dump(creds, token)

        service = build("calendar", "v3", credentials=creds)

        manila_tz = pytz.timezone("Asia/Manila")
        start_time = datetime.now(manila_tz) + timedelta(minutes=minutes_from_now)
        end_time = start_time + timedelta(minutes=30)

        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Manila"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Manila"},
        }

        created_event = service.events().insert(calendarId="primary", body=event).execute()

        if created_event and created_event.get("id"):
            event_link = created_event.get("htmlLink")
            logging.info(f"✅ Event created successfully: {event_link}")
            print(f"✅ Google Calendar event created: {event_link}")
            return f"📅 Task '{title}' scheduled successfully in Google Calendar!\nLink: {event_link}"
        else:
            raise Exception("No event ID returned — API response invalid.")

    except Exception as e:
        logging.error(f"❌ Error scheduling event: {e}")
        return f"❌ Failed to schedule task: {str(e)}"

# ----------------------------------------------------------
# DEBUG INFO
# ----------------------------------------------------------
print("LIVEKIT_URL:", os.getenv("LIVEKIT_URL"))
print(f"Google Credentials located at: {CREDENTIALS_PATH}")
