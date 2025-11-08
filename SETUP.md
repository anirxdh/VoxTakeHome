# Voxology Setup Guide

This guide explains how to run the voice agent application with backend and frontend connected.


## Architecture

- **Backend**: `agent-starter-python/` - LiveKit Agent (Python)
- **Frontend**: `vox-takehome-test/` - Next.js UI

## Prerequisites

1. LiveKit Cloud account with credentials
2. Python 3.12+ with `uv` installed
3. Node.js 18+ with npm/pnpm

## Setup Steps

### 1. Configure Environment Variables

**Backend** (`agent-starter-python/.env.local`):
```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# Provider API keys
OPENAI_API_KEY=your_openai_key
CARTESIA_API_KEY=your_cartesia_key
ASSEMBLYAI_API_KEY=your_assemblyai_key
```

**Frontend** (`vox-takehome-test/.env.local`):
```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
```

### 2. Start the Backend Agent

Open a terminal and run:

```bash
cd agent-starter-python
uv run python src/agent.py dev
```

You should see output indicating the agent is running and connected to LiveKit Cloud.

### 3. Start the Frontend

Open a **separate** terminal and run:

```bash
cd vox-takehome-test
npm run dev
# or: pnpm dev
```

The frontend should start on `http://localhost:3000`

### 4. Test the Connection

1. Open `http://localhost:3000` in your browser
2. Click "Start call"
3. Allow microphone permissions
4. Speak to the agent - it should respond!

## How It Works

1. **Frontend** starts a call and requests connection details from `/api/connection-details`
2. The API creates a LiveKit room token with agent configuration (agent name: `agent-starter-python`)
3. **LiveKit Cloud** receives the room creation request and dispatches your running agent
4. **Agent** joins the room and begins the voice conversation
5. Audio flows: User → Frontend → LiveKit Cloud → Agent → LiveKit Cloud → Frontend → User

## Troubleshooting

### Agent not joining the room?
- Check that the backend agent is running (`uv run python src/agent.py dev`)
- Verify the agent name in `vox-takehome-test/app-config.ts` matches your agent
- Check backend console for errors

### Can't hear the agent?
- Check browser console for WebRTC errors
- Verify microphone permissions are granted
- Check that API keys for TTS/STT providers are valid

### Connection timeouts?
- Verify LiveKit credentials are correct in both `.env.local` files
- Check that `LIVEKIT_URL` uses `wss://` protocol
- Ensure you're using the same LiveKit project for both backend and frontend

## Development Tips

- Keep both terminals visible to monitor logs from both services
- The backend agent shows detailed logs about LLM, TTS, and STT operations
- Frontend console shows LiveKit room connection status and events
- Check the LiveKit Cloud dashboard to see active rooms and agents

## Next Steps

- Modify agent instructions in `agent-starter-python/src/agent.py`
- Customize the UI in `vox-takehome-test/components/`
- Add custom tools to the agent using `@function_tool` decorator

