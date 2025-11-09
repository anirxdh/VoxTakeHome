import os
import logging
from twilio.rest import Client

logger = logging.getLogger("sms")


class SMSSender:
    """Helper class for sending SMS messages via Twilio"""
    
    def __init__(self):
        """Initialize Twilio client with credentials from environment variables"""
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([account_sid, auth_token, self.from_number]):
            logger.warning("Twilio credentials not fully configured in environment variables")
        
        self.client = Client(account_sid, auth_token)
        logger.info("Twilio SMS client initialized")
    
    def send_appointment_confirmation(self, to_phone: str, first_name: str,
                                     provider_name: str, appointment_time: str):
        """Send appointment confirmation SMS.
        
        Args:
            to_phone: Recipient's phone number (E.164 format, e.g., +1234567890)
            first_name: Recipient's first name for personalization
            provider_name: Healthcare provider's full name
            appointment_time: Formatted appointment date and time string
        
        Returns:
            bool: True if SMS sent successfully, False otherwise
        """
        # Create concise message (SMS has character limits)
        message_body = (
            f"Hi {first_name}, your appointment with {provider_name} "
            f"is confirmed for {appointment_time}. - Voxology Healthcare"
        )
        
        try:
            # Send SMS via Twilio
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=to_phone
            )
            logger.info(f"SMS sent successfully to {to_phone}, SID: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_phone}: {e}")
            return False

