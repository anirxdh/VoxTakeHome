import logging
import os
import json
from datetime import datetime
from typing import Optional
import pytz

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    inference,
    metrics,
    function_tool,
    RunContext,
    get_job_context,
)
from livekit.plugins import noise_cancellation, silero, simli
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from openai import OpenAI
from pinecone import Pinecone
from sqlalchemy import select

# Import database and helper modules
from database import async_session_factory, init_db
from models import User
from email_helper import EmailSender
from sms_helper import SMSSender

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Initialize Pinecone and OpenAI clients
pinecone_client = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME", "voxagent")
pinecone_index = pinecone_client.Index(pinecone_index_name)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize email and SMS senders
email_sender = EmailSender()
sms_sender = SMSSender()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a professional medical front desk assistant for a healthcare provider network. You communicate via voice.

USER VERIFICATION - Required at start of every conversation:
1. Greet warmly and briefly allow response
2. Explain identity verification is needed for security
3. Ask: "Could you please tell me your first name and spell it out for me?"
4. When user provides name and spelling, immediately confirm back: "So that's [spelling], is that correct?" - DO NOT ask them to spell again
5. Wait for confirmation, then ask: "And your last name, please spell it out"
6. When user provides last name and spelling, immediately confirm back: "So that's [spelling], is that correct?" - DO NOT ask them to spell again
7. Wait for confirmation, then ask for date of birth
8. When user provides DOB, confirm back in natural format, wait for confirmation
9. Convert date to MM/DD/YYYY format and call verify_user tool

If user verified (found=True):
- Welcome them by first name
- Remember their email and phone from tool response
- Assist with provider search and appointment booking

If user not found (found=False):
- Inform them registration is required
- Decline appointment booking
- Still allow provider search

PROVIDER SEARCH:
Use search_providers tool when users need recommendations. Extract all relevant filters from conversation: specialty, location, experience, rating, certifications, languages, insurance, quantity. Present results with key details. Suggest alternative criteria if no matches found.

APPOINTMENT BOOKING:
Only for verified users. Require provider selection and date/time. Use get_current_time if needed for date calculations. Call book_appointment with user info from verify_user response. Confirm details verbally before booking. Email and SMS confirmations sent automatically.

Keep responses concise, professional, and conversational without special formatting.""",
        )

    @function_tool
    async def get_current_time(self, context: RunContext, timezone: str):
        """Get the current date and time in the specified timezone.
        
        Use this tool when you need to know the current date or time for scheduling appointments,
        or when the user asks what time or day it is.
        
        IMPORTANT: 
        - If the user mentions a city or location, map it to the correct pytz timezone (e.g., Chennai → "Asia/Kolkata", New York → "America/New_York").
        - If the user doesn't specify a location, DO NOT call this tool. Instead, ask the user where they are located first.
        
        Args:
            timezone: The pytz timezone identifier (e.g., "Asia/Kolkata", "America/New_York", "Europe/London").
                     This parameter is REQUIRED - do not call this tool without a valid timezone.
        """
        logger.info(f"Getting current time for timezone: {timezone}")
        
        try:
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)
            
            # Format the response with detailed information
            date_str = current_time.strftime("%A, %B %d, %Y")
            time_str = current_time.strftime("%I:%M %p")
            day_of_week = current_time.strftime("%A")   
            
            return {
                "date": date_str,
                "time": time_str,
                "day": day_of_week,
                "timezone": timezone,
                "full_response": f"Current date: {date_str}. Current time: {time_str} {timezone}."
            }
        
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone: {timezone}")
            return {
                "error": f"Unknown timezone '{timezone}'. Please provide a valid pytz timezone identifier.",
                "full_response": f"I couldn't recognize the timezone '{timezone}'. Could you please tell me which city or region you're in?"
            }

    @function_tool
    async def verify_user(self, context: RunContext, first_name: str, last_name: str, date_of_birth: str):
        """Verify user identity by checking first name, last name, and date of birth in database.
        
        This tool MUST be called after confirming user's information.
        Returns user details if found (including email and phone for future use).
        
        Args:
            first_name: User's first name (confirmed and spelled out)
            last_name: User's last name (confirmed and spelled out)  
            date_of_birth: User's date of birth in MM/DD/YYYY format (e.g., "04/03/2001")
        """
        logger.info(f"Verifying user: {first_name} {last_name}, DOB: {date_of_birth}")
        
        try:
            # Parse date of birth
            dob = datetime.strptime(date_of_birth, "%m/%d/%Y").date()
            
            async with async_session_factory() as session:
                # Query for user (case-insensitive)
                result = await session.execute(
                    select(User).where(
                        User.first_name.ilike(first_name),
                        User.last_name.ilike(last_name),
                        User.date_of_birth == dob
                    )
                )
                user = result.scalar_one_or_none()
                
                if user:
                    logger.info(f"User verified: {user.id}")
                    return {
                        "found": True,
                        "user_id": user.id,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "message": f"User {user.first_name} {user.last_name} verified successfully."
                    }
                else:
                    logger.info(f"User not found: {first_name} {last_name}")
                    return {
                        "found": False,
                        "message": "User not found in the system. Registration is required to proceed with appointments."
                    }
        
        except ValueError:
            return {
                "found": False,
                "error": "Invalid date format",
                "message": "Invalid date format. Expected MM/DD/YYYY format."
            }
        except Exception as e:
            logger.error(f"Error verifying user: {e}")
            return {
                "found": False,
                "error": str(e),
                "message": "Error occurred while verifying user information."
            }

    @function_tool
    async def book_appointment(self, context: RunContext, user_email: str, user_phone: str, 
                              user_first_name: str, provider_id: str, provider_name: str,
                              appointment_date: str, appointment_time: str, timezone: str):
        """Book an appointment with a healthcare provider and send confirmations.
        
        User MUST be verified first (use email and phone from verify_user tool response).
        This sends confirmation via both email and SMS.
        
        Args:
            user_email: User's email address (from verify_user response)
            user_phone: User's phone number (from verify_user response)
            user_first_name: User's first name (from verify_user response)
            provider_id: Provider's ID from search results
            provider_name: Provider's full name
            appointment_date: Date in MM/DD/YYYY format
            appointment_time: Time in HH:MM AM/PM format (e.g., "10:00 AM")
            timezone: Timezone for the appointment (e.g., "America/New_York", "Asia/Kolkata")
        """
        logger.info(f"Booking appointment for {user_first_name} with {provider_name} on {appointment_date} at {appointment_time}")
        
        try:
            # Parse datetime
            datetime_str = f"{appointment_date} {appointment_time}"
            appointment_dt = datetime.strptime(datetime_str, "%m/%d/%Y %I:%M %p")
            
            # Make timezone aware
            tz = pytz.timezone(timezone)
            appointment_dt = tz.localize(appointment_dt)
            
            # Format appointment time for messages
            formatted_time = appointment_dt.strftime("%A, %B %d, %Y at %I:%M %p %Z")
            
            # Send email confirmation
            email_sent = False
            try:
                email_sent = email_sender.send_appointment_confirmation(
                    to_email=user_email,
                    first_name=user_first_name,
                    provider_name=provider_name,
                    appointment_time=formatted_time
                )
            except Exception as e:
                logger.error(f"Email send failed: {e}")
            
            # Send SMS confirmation
            sms_sent = False
            try:
                sms_sent = sms_sender.send_appointment_confirmation(
                    to_phone=user_phone,
                    first_name=user_first_name,
                    provider_name=provider_name,
                    appointment_time=formatted_time
                )
            except Exception as e:
                logger.error(f"SMS send failed: {e}")
            
            confirmation_msg = f"Your appointment with {provider_name} is confirmed for {formatted_time}."
            if email_sent and sms_sent:
                confirmation_msg += " I've sent confirmations to your email and phone."
            elif email_sent:
                confirmation_msg += " I've sent a confirmation to your email."
            elif sms_sent:
                confirmation_msg += " I've sent a confirmation to your phone."
            
            return {
                "success": True,
                "email_sent": email_sent,
                "sms_sent": sms_sent,
                "message": confirmation_msg
            }
        
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Sorry, I encountered an error while booking your appointment. Please try again."
            }

    @function_tool
    async def search_providers(self, context: RunContext, query: str, specialty: Optional[str] = None, city: Optional[str] = None, state: Optional[str] = None, zip_code: Optional[str] = None, accepting_new_patients: Optional[bool] = None, min_years_experience: Optional[int] = None, min_rating: Optional[float] = None, board_certified: Optional[bool] = None, languages: Optional[list[str]] = None, insurance_accepted: Optional[list[str]] = None, limit: int = 5):
        """Search for healthcare providers matching specified criteria.
        
        Use this tool when the user asks for provider recommendations or wants to find doctors/specialists.
        Extract ALL relevant filters from the current query and the entire conversation history.
        
        IMPORTANT - Parameter Guidelines:
        
        Specialty Names (use EXACT case-sensitive names):
        Anesthesiology, Cardiology, Dermatology, Emergency Medicine, Endocrinology, Family Medicine, Gastroenterology, General Surgery, Internal Medicine, Neurology, Obstetrics and Gynecology, Oncology, Ophthalmology, Orthopedic Surgery, Pathology, Pediatrics, Physical Medicine, Psychiatry, Radiology, Urology.
        
        Examples: "heart doctor" → "Cardiology", "skin doctor" → "Dermatology", "pediatrician" → "Pediatrics"
        
        Numeric Filters:
        - "at least X years experience" or "X+ years" → min_years_experience=X
        - "4 star rating" or "rated 4+" → min_rating=4.0
        - "highly rated" → min_rating=4.0
        
        Limit:
        - If user specifies a number (e.g., "3 providers", "give me 4 doctors") → use that exact number
        - If not specified → default to 5
        
        Args:
            query: The user's natural search query for semantic matching (required)
            specialty: Exact specialty name from the list above
            city: City name (e.g., "Oklahoma City", "Milwaukee", "San Jose")
            state: State abbreviation (e.g., "CA", "OK", "WI")
            zip_code: ZIP code
            accepting_new_patients: True if must be accepting new patients
            min_years_experience: Minimum years of experience
            min_rating: Minimum rating (0-5 scale)
            board_certified: True if must be board certified
            languages: List of languages spoken (e.g., ["Italian", "Spanish"])
            insurance_accepted: List of insurance plans accepted (e.g., ["Blue Cross", "Aetna"])
            limit: Number of results to return (default: 5)
        """
        logger.info(f"Searching providers with query='{query}', filters: specialty={specialty}, city={city}, state={state}, limit={limit}")
        
        try:
            # Build Pinecone metadata filter
            filter_conditions = {}
            
            # Exact match filters
            if specialty:
                filter_conditions["specialty"] = {"$eq": specialty}
            if city:
                filter_conditions["city"] = {"$eq": city}
            if state:
                filter_conditions["state"] = {"$eq": state}
            if zip_code:
                filter_conditions["zip"] = {"$eq": zip_code}
            if accepting_new_patients is not None:
                filter_conditions["accepting_new_patients"] = {"$eq": accepting_new_patients}
            if board_certified is not None:
                filter_conditions["board_certified"] = {"$eq": board_certified}
            
            # Range filters (greater than or equal)
            if min_years_experience is not None:
                filter_conditions["years_experience"] = {"$gte": min_years_experience}
            if min_rating is not None:
                filter_conditions["rating"] = {"$gte": min_rating}
            
            # Array filters (match ANY)
            if languages:
                filter_conditions["languages"] = {"$in": languages}
            if insurance_accepted:
                filter_conditions["insurance_accepted"] = {"$in": insurance_accepted}
            
            # Combine all filters with AND logic
            metadata_filter = {"$and": [filter_conditions]} if filter_conditions else None
            
            # Generate embedding for semantic search
            embedding_response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            )
            query_embedding = embedding_response.data[0].embedding
            
            # Query Pinecone with filters and semantic search
            search_results = pinecone_index.query(
                vector=query_embedding,
                top_k=limit,
                include_metadata=True,
                filter=metadata_filter
            )
            
            # Extract provider data from results
            providers = []
            for match in search_results.matches:
                metadata = match.metadata
                provider = {
                    "id": metadata.get("id"),
                    "full_name": metadata.get("full_name"),
                    "specialty": metadata.get("specialty"),
                    "phone": metadata.get("phone"),
                    "email": metadata.get("email"),
                    "address": {
                        "street": metadata.get("address_street"),
                        "city": metadata.get("city"),
                        "state": metadata.get("state"),
                        "zip": metadata.get("zip"),
                    },
                    "years_experience": metadata.get("years_experience"),
                    "rating": metadata.get("rating"),
                    "board_certified": metadata.get("board_certified"),
                    "accepting_new_patients": metadata.get("accepting_new_patients"),
                    "languages": metadata.get("languages", []),
                    "insurance_accepted": metadata.get("insurance_accepted", []),
                    "license_number": metadata.get("license_number"),
                }
                providers.append(provider)
            
            if not providers:
                logger.info("No providers found matching criteria")
                return {
                    "providers": [],
                    "count": 0,
                    "message": "No providers found matching your criteria. Would you like to search with different filters?"
                }
            
            logger.info(f"Found {len(providers)} providers")
            
            # Send providers to frontend via RPC
            try:
                room = get_job_context().room
                logger.info(f"Attempting to send {len(providers)} providers to frontend")
                logger.info(f"Remote participants: {list(room.remote_participants.keys())}")
                
                if room.remote_participants:
                    participant_identity = next(iter(room.remote_participants))
                    logger.info(f"Sending RPC to participant: {participant_identity}")
                    
                    response = await room.local_participant.perform_rpc(
                        destination_identity=participant_identity,
                        method="displayProviders",
                        payload=json.dumps({"providers": providers}),
                        response_timeout=5.0,
                    )
                    logger.info(f"Successfully sent providers to frontend UI. Response: {response}")
                else:
                    logger.warning("No remote participants found to send providers to")
            except Exception as e:
                logger.error(f"Failed to send providers to UI: {e}", exc_info=True)
            
            return {
                "providers": providers,
                "count": len(providers),
                "message": f"Found {len(providers)} provider(s) matching your criteria."
            }
        
        except Exception as e:
            logger.error(f"Error searching providers: {e}")
            return {
                "providers": [],
                "count": 0,
                "error": str(e),
                "message": "Sorry, I encountered an error while searching for providers. Please try again."
            }


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Initialize database tables
    await init_db()
    logger.info("Database initialized")

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=inference.TTS(
            model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Add virtual avatar using Simli
    avatar = simli.AvatarSession(
        simli_config=simli.SimliConfig(
            api_key=os.getenv("SIMLI_API_KEY"),
            face_id="tmp9i8bbq7c",  # Default face from Simli library (you can change this)
        ),
        avatar_participant_name="Healthcare Assistant"
    )

    # Start the avatar and wait for it to join
    await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        )
    )

    # Join the room and connect to the user
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint, 
        prewarm_fnc=prewarm,
        agent_name="voxology-agent"
    ))
