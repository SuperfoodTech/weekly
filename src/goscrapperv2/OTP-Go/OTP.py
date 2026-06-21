import os
import re
import time
import pickle
import requests
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv

# Load root .env first, fallback to current directory .env
parent_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(parent_env):
    load_dotenv(parent_env)
else:
    load_dotenv()

# Initialize Rich Console
console = Console()

# If modifying these scopes, delete the file token.pickle.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly'
]

# --- CONFIGURATION ---
WEB_APP_URL = os.getenv("OTP_ENDPOINT_URL", 'https://script.google.com/macros/s/AKfycbyPgVKDxRa3d5_Z-0Y41LHYIM3dys__OOTC6gdYUkXckiShzdztQOiCgZthuWHs020d/exec')
SENDER_NAME = os.getenv("GMAIL_OTP_SENDER", "Gojek untuk Mitra Usaha")
GMAIL_LABEL = os.getenv("GMAIL_OTP_LABEL", "OTP-GO")
# ---------------------

def get_credentials():
    creds = None
    # token.pickle stores the user's access and refresh tokens.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                console.print("[bold red]Error: 'credentials.json' not found in OTP-Go directory.[/bold red]")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def get_latest_otp(gmail_service):
    if GMAIL_LABEL:
        query = f'label:"{GMAIL_LABEL}"'
    else:
        query = f'from:"{SENDER_NAME}"'
    try:
        results = gmail_service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])

        if not messages:
            return None

        msg_id = messages[0]['id']
        msg = gmail_service.users().messages().get(userId='me', id=msg_id).execute()
        
        # Get Internal Date (Email Arrival)
        internal_date = int(msg.get('internalDate', 0)) / 1000
        received_at = datetime.fromtimestamp(internal_date).strftime("%Y-%m-%d %H:%M:%S")

        # Get Sender from Headers
        headers = msg.get('payload', {}).get('headers', [])
        sender = next((header['value'] for header in headers if header['name'].lower() == 'from'), SENDER_NAME)

        # Get Body (Snippet)
        snippet = msg.get('snippet', '')
        
        # Try to get full body if snippet is too short or for better detail
        body_text = snippet
        payload = msg.get('payload', {})
        parts = payload.get('parts', [])
        for part in parts:
            if part.get('mimeType') == 'text/plain':
                import base64
                data = base64.urlsafe_b64decode(part.get('body', {}).get('data', '')).decode('utf-8')
                body_text = data
                break

        # Regex to find 4 or 6 digit codes
        match = re.search(r'\b\d{4,6}\b', body_text)
        
        if not match and snippet != body_text:
            match = re.search(r'\b\d{4,6}\b', snippet)

        if match:
            return {
                'otp': match.group(0),
                'received_at': received_at,
                'sender': sender,
                'body': body_text[:1000], # Truncate body to 1000 chars for sheet safety
                'id': msg_id
            }
    except Exception as e:
        console.print(f"[red]Error fetching Gmail: {e}[/red]")
    return None

def send_to_sheet(otp_data):
    try:
        response = requests.post(WEB_APP_URL, json=otp_data)
        if response.status_code == 200:
            return True
        else:
            console.print(f"[red]Error writing to Sheet. Status Code: {response.status_code}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]Error writing to Sheet: {e}[/red]")
        return False

def main():
    console.print(Panel.fit("OTP Receiver & Forwarder", style="bold blue"))
    
    creds = get_credentials()
    if not creds:
        return

    gmail_service = build('gmail', 'v1', credentials=creds)
    
    console.print(f"[green]Successfully authenticated.[/green]")
    if GMAIL_LABEL:
        console.print(f"Monitoring emails matching label: [bold cyan]{GMAIL_LABEL}[/bold cyan]")
    else:
        console.print(f"Monitoring emails from: [bold cyan]{SENDER_NAME}[/bold cyan]")
    console.print(f"Target Web App URL: [bold cyan]{WEB_APP_URL}[/bold cyan]")
    
    last_msg_id = None
    
    while True:
        try:
            otp_data = get_latest_otp(gmail_service)
            
            if otp_data and otp_data['id'] != last_msg_id:
                console.print(f"[bold green][{datetime.now().strftime('%H:%M:%S')}] New OTP Detected: {otp_data['otp']}[/bold green]")
                if send_to_sheet(otp_data):
                    console.print(f"[blue]Successfully updated sheet with details.[/blue]")
                last_msg_id = otp_data['id']
            else:
                pass
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping service...[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Unexpected error: {e}[/red]")
            
        time.sleep(5) # Check every 5 seconds

if __name__ == '__main__':
    # Change CWD to the directory of the script to find credentials.json
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
