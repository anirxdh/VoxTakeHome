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

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Initialize Pinecone and OpenAI clients
pinecone_client = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME", "voxagent")
pinecone_index = pinecone_client.Index(pinecone_index_name)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant for a healthcare provider search service. The user is interacting with you via voice, even if you perceive the conversation as text.
            You help users find healthcare providers based on their needs and preferences.
            
            When a user asks for provider recommendations, use the search_providers tool to find matching providers.
            Pay attention to ALL relevant details mentioned throughout the conversation, including:
            - Specialty (e.g., Cardiology, General Surgery, Pediatrics)
            - Location (city, state, zip code)
            - Requirements (years of experience, rating, accepting new patients, board certification)
            - Languages spoken
            - Insurance accepted
            - Number of providers requested
            
            After receiving search results, present them naturally with key details like name, specialty, phone number, and location.
            If no providers are found, politely inform the user and suggest they try different criteria.
            
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, professional, and helpful.""",
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
                if room.remote_participants:
                    participant_identity = next(iter(room.remote_participants))
                    await room.local_participant.perform_rpc(
                        destination_identity=participant_identity,
                        method="displayProviders",
                        payload=json.dumps({"providers": providers}),
                        response_timeout=5.0,
                    )
                    logger.info("Successfully sent providers to frontend UI")
            except Exception as e:
                logger.warning(f"Failed to send providers to UI: {e}")
            
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
