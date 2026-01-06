# WWII Multi-Agent Simulation

A WWII strategy game where you control one of three major powers (Germany, UK, or USSR) while AI agents control the others. Built with LangChain, LangGraph, and FastAPI.

## What is this?

This is a turn-based strategy game set in WWII. Each turn, you and two AI opponents choose actions from dynamically generated options. The game uses LLMs to generate historically-grounded events and simulate intelligent opponents with distinct personalities.

Key features:
- Three playable nations with AI-controlled opponents
- Dynamic event generation using RAG (retrieval from 515+ historical events)
- Multi-agent system with personality-driven decision making
- Turn-based gameplay with resource management
- AI-generated endings based on your strategic choices

## Requirements

- Python 3.10+
- LM Studio (recommended) or OpenAI API key

## Installation

```bash
# Clone the repository
git clone https://github.com/Acmaro/WWII-Sim.git
cd WWII-Sim

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

## Running the Game

Start the backend server:
```bash
uvicorn backend.api.multi_agent_server:app --reload --port 8000
```

Open `frontend/multi_agent.html` in your browser.

## How to Play

1. Select your country (Germany, UK, or USSR)
2. Each turn, the game generates 4 strategic options for all countries
3. AI opponents automatically choose based on their personalities
4. You select your action
5. All actions are resolved simultaneously
6. Resources change, diplomatic relations shift, and the game continues

The game ends when:
- A country's resources are depleted
- Time limit is reached (1945)
- You trigger an ending manually

## Configuration

Edit `.env` to configure:

- `LLM_PROVIDER`: "lm_studio" (local, free) or "openai" (cloud, paid)
- `LM_STUDIO_BASE_URL`: Your LM Studio endpoint (default: http://localhost:1234/v1)
- `OPENAI_API_KEY`: Your OpenAI key (if using OpenAI)

For LM Studio:
1. Download and run LM Studio
2. Load a model (qwen2.5:14b recommended)
3. Start the local server
4. Keep the default settings in .env

## Tech Stack

Backend: FastAPI, LangChain, LangGraph, Pydantic
Frontend: Vanilla JavaScript, D3.js
AI: LLM (local or cloud), FAISS vector database
Data: 515+ historical WWII events for RAG

## Architecture

The game uses LangGraph workflows to generate events. Each workflow:
1. Retrieves relevant historical context from FAISS
2. Generates 4 option branches using LLM
3. Validates output quality
4. Iteratively refines if needed (up to 3 iterations)

AI opponents use personality-based decision making:
- Aggression level (affects military action preference)
- Diplomatic tendency (affects negotiation preference)
- Economic focus (affects development preference)
- Risk tolerance (affects bold vs conservative choices)

## Development

The project is organized as:
- `backend/core/`: Data models, configuration, LLM setup
- `backend/workflows/`: LangGraph event generation
- `backend/services/`: Knowledge base, ending generator
- `backend/api/`: FastAPI servers
- `frontend/`: HTML/JavaScript interface
- `data/`: Historical events database

## License

MIT
