import os
import pickle
import base64
import logging
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger("email")

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


class EmailSender:
    """Helper class for sending emails via Gmail API"""
    
    def __init__(self):
        self.credentials_file = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
        self.token_file = os.getenv("GMAIL_TOKEN_FILE", "token.pickle")
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.service = None
    
    def authenticate(self):
        """Authenticate with Gmail API using OAuth2.
        
        Loads existing credentials from token file if available.
        If not available or expired, initiates OAuth flow to get new credentials.
        Saves credentials to token file for future use.
        """
        creds = None
        
        # Load existing token if it exists
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Refresh expired credentials
                creds.refresh(Request())
                logger.info("Refreshed Gmail credentials")
            else:
                # Get new credentials via OAuth flow
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                # Use port 8080 to match configured redirect URI
                creds = flow.run_local_server(port=8080, open_browser=True)
                logger.info("Obtained new Gmail credentials")
            
            # Save credentials for future use
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        # Build Gmail API service
        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail authentication successful")
    
    def send_appointment_confirmation(self, to_email: str, first_name: str, 
                                     provider_name: str, appointment_time: str):
        """Send appointment confirmation email.
        
        Args:
            to_email: Recipient's email address
            first_name: Recipient's first name for personalization
            provider_name: Healthcare provider's full name
            appointment_time: Formatted appointment date and time string
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.service:
            self.authenticate()
        
        subject = "Appointment Confirmation - Voxology Healthcare"
        
        # Create email body with HTML formatting
        body = f"""
        <html>
        <body>
            <h2>Appointment Confirmation</h2>
            <p>Dear {first_name},</p>
            
            <p>Your appointment has been successfully booked!</p>
            
            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <strong>Provider:</strong> {provider_name}<br>
                <strong>Date & Time:</strong> {appointment_time}
            </div>
            
            <p>If you need to reschedule or cancel, please contact our office.</p>
            
            <p>Best regards,<br>
            Voxology Healthcare Team</p>
        </body>
        </html>
        """
        
        # Create MIME message
        message = MIMEText(body, 'html')
        message['to'] = to_email
        message['from'] = self.sender_email
        message['subject'] = subject
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        try:
            # Send email via Gmail API
            sent_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            logger.info(f"Email sent successfully to {to_email}, message ID: {sent_message['id']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

