# tools.py
import logging
from livekit.agents import function_tool, RunContext
import requests
from langchain_community.tools import DuckDuckGoSearchRun
import os
import smtplib
from email.mime.multipart import MIMEMultipart  
from email.mime.text import MIMEText
from typing import Optional
import subprocess
from datetime import datetime, timedelta
import threading
import asyncio

# --- Open Apps ---
@function_tool()
async def open_app(
    context: RunContext,  # type: ignore
    app_name: str
) -> str:
    """
    Open a Windows application by name.
    """
    apps = {
        "notepad": r"C:\Windows\System32\notepad.exe",
        "calculator": r"C:\Windows\System32\calc.exe",
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        # Add more apps here
    }
    path = apps.get(app_name.lower())
    if not path:
        return f"App '{app_name}' not recognized."

    try:
        subprocess.Popen([path])
        logging.info(f"App '{app_name}' opened successfully")
        return f"{app_name} opened successfully!"
    except Exception as e:
        logging.error(f"Failed to open {app_name}: {e}")
        return f"Failed to open {app_name}: {e}"

# --- Task Scheduling / Reminders ---
reminders = []

@function_tool()
async def set_reminder(
    context: RunContext,  # type: ignore
    task: str,
    minutes: int
) -> str:
    """
    Set a reminder task with a time in minutes.
    """
    reminder_time = datetime.now() + timedelta(minutes=minutes)
    reminders.append((task, reminder_time))

    def reminder_checker(task, reminder_time):
        while datetime.now() < reminder_time:
            pass
        print(f"[REMINDER] {task}")  # Could be replaced with LiveKit TTS
    
    threading.Thread(target=reminder_checker, args=(task, reminder_time), daemon=True).start()
    logging.info(f"Reminder set: '{task}' in {minutes} minutes")
    return f"Reminder set for '{task}' in {minutes} minutes."

# --- Personalized Greeting ---
@function_tool()
async def greet_user(
    context: RunContext,  # type: ignore
    user_name: str = "User"
) -> str:
    """
    Return a personalized greeting with number of reminders.
    """
    now = datetime.now()
    greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
    return f"{greeting}, {user_name}! You have {len(reminders)} reminders today."

# --- Web Search ---
@function_tool()
async def search_web(
    context: RunContext,  # type: ignore
    query: str
) -> str:
    """
    Search the web using DuckDuckGo.
    """
    try:
        results = DuckDuckGoSearchRun().run(tool_input=query)
        logging.info(f"Search results for '{query}': {results}")
        return results
    except Exception as e:
        logging.error(f"Error searching the web for '{query}': {e}")
        return f"An error occurred while searching the web for '{query}'."

# --- Get Weather ---
@function_tool()
async def get_weather(
    context: RunContext,  # type: ignore
    city: str
) -> str:
    """
    Get the current weather for a given city.
    """
    try:
        response = requests.get(f"https://wttr.in/{city}?format=3")
        if response.status_code == 200:
            logging.info(f"Weather for {city}: {response.text.strip()}")
            return response.text.strip()   
        else:
            logging.error(f"Failed to get weather for {city}: {response.status_code}")
            return f"Could not retrieve weather for {city}."
    except Exception as e:
        logging.error(f"Error retrieving weather for {city}: {e}")
        return f"An error occurred while retrieving weather for {city}." 

# --- Send Email ---
@function_tool()    
async def send_email(
    context: RunContext,  # type: ignore
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None
) -> str:
    """
    Send an email through Gmail.
    """
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

# Debug print
import os
print("LIVEKIT_URL:", os.getenv("LIVEKIT_URL"))
