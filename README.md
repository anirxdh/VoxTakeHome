# Voxology Voice Agent

A healthcare voice assistant that helps users find providers and book appointments through natural conversation.

## 🚀 Quick Start

### Prerequisites

- **LiveKit Cloud Account** - Sign up at [cloud.livekit.io](https://cloud.livekit.io)
- **Python 3.12+** with `uv` package manager
- **Node.js 18+** with npm or pnpm
- **API Keys**: OpenAI, Pinecone, Simli (for avatar)

### Setup (5 minutes)

#### 1. Configure Environment Variables

**Backend** (`agent-starter-python/.env.local`):
```bash
# LiveKit Credentials (get from LiveKit Cloud dashboard)
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# AI Service Keys
OPENAI_API_KEY=your_openai_key
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=voxagent
SIMLI_API_KEY=your_simli_key

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/voxology
```

**Frontend** (`vox-takehome-test/.env.local`):
```bash
# LiveKit Credentials (same as backend)
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
```

#### 2. Install Dependencies

**Backend:**
```bash
cd agent-starter-python
uv sync
```

**Frontend:**
```bash
cd vox-takehome-test
npm install
# or: pnpm install
```

#### 3. Set Up Database

```bash
cd agent-starter-python
# Create database tables
uv run python -c "from src.database import init_db; import asyncio; asyncio.run(init_db())"
```

#### 4. Run the Application

**Terminal 1 - Start Backend Agent:**
```bash
cd agent-starter-python
uv run python src/agent.py dev
```

**Terminal 2 - Start Frontend:**
```bash
cd vox-takehome-test
npm run dev
# or: pnpm dev
```

#### 5. Open in Browser

Visit [http://localhost:3000](http://localhost:3000) and click **"Start call"**

## 📁 Project Structure

```
Voxology/
├── agent-starter-python/    # Python voice agent backend
│   ├── src/
│   │   ├── agent.py         # Main agent logic & tools
│   │   ├── database.py      # Database setup
│   │   └── models.py        # User data models
│   └── scripts/
│       └── embed_providers.py  # Provider data embedding
│
└── vox-takehome-test/       # Next.js frontend
    ├── components/          # React components
    ├── app/                 # Next.js app router
    └── data/
        └── providerlist.json  # Provider database
```

## 🎯 Features

- **Voice Conversation** - Natural language interaction with the agent
- **Provider Search** - Find healthcare providers by specialty, location, and more
- **User Verification** - Secure identity verification before booking
- **Appointment Booking** - Schedule appointments with email/SMS confirmations
- **Virtual Avatar** - Visual representation of the agent
- **Provider Modal** - View detailed provider information in the UI

## 💬 Example Conversations

**Search for providers:**
- "Can you find me 2 cardiologists in Oklahoma City?"
- "Show me doctors in Milwaukee who do general surgery"
- "I need a pediatrician with at least 10 years experience"

**Book appointment:**
- "I'd like to book an appointment with Dr. Smith"
- "Schedule me for next Tuesday at 2pm"

## 🔧 Troubleshooting

### Agent not joining?
- ✅ Check backend terminal is running (`uv run python src/agent.py dev`)
- ✅ Verify agent name in `vox-takehome-test/app-config.ts` matches your agent
- ✅ Check LiveKit credentials are correct in both `.env.local` files

### Can't hear the agent?
- ✅ Allow microphone permissions in browser
- ✅ Check browser console for errors
- ✅ Verify TTS/STT API keys are valid

### Connection errors?
- ✅ Ensure `LIVEKIT_URL` uses `wss://` protocol (not `https://`)
- ✅ Verify you're using the same LiveKit project for both frontend and backend
- ✅ Check LiveKit Cloud dashboard for active rooms

## 📚 Learn More

- [LiveKit Agents Documentation](https://docs.livekit.io/agents)
- [LiveKit Cloud Dashboard](https://cloud.livekit.io)
- [Frontend README](./vox-takehome-test/README.md)
- [Backend README](./agent-starter-python/README.md)

## 🛠️ Development

### Adding New Tools

Edit `agent-starter-python/src/agent.py` and add a new function with `@function_tool` decorator:

```python
@function_tool
async def my_new_tool(self, context: RunContext, param: str):
    """Tool description for the LLM"""
    # Your logic here
    return {"result": "success"}
```

### Customizing UI

Edit components in `vox-takehome-test/components/`:
- `session-view.tsx` - Main session interface
- `provider-modal.tsx` - Provider details display
- `app-config.ts` - App configuration and branding

## 📝 License

MIT License - See LICENSE files in respective directories
