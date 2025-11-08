# Real Estate AI Assistant

A production-quality multi-agent AI system using LangGraph orchestration with custom MCP (Model Context Protocol) servers for intelligent real estate assistance.

**Inspired by Zillow's Agentic AI initiative - built with production-grade architecture and best practices.**

🌐 **Live Demo**: [https://zillow-agent-demo.streamlit.app/](https://zillow-agent-demo.streamlit.app/)

![Real Estate AI Assistant UI](docs/images/streamlit-ui-screenshot.png)

*Streamlit UI showing property search results with AI analysis, school information, and market trends*

## 🎯 Project Overview

This project showcases advanced AI system architecture including:

- Multi-agent coordination via LangGraph state machines
- Custom MCP servers for structured data access
- Production-ready error handling and logging
- Comprehensive testing and documentation
- Real-time conversation with context memory

## 🏗️ Architecture

### Components

1. **MCP Servers** (Data Layer)
   - Real Estate Data Server
   - Market Analysis Server
   - User Context Server

2. **Agent System** (Logic Layer)
   - Search Agent
   - Analysis Agent
   - Advisor Agent
   - Coordinator (LangGraph orchestration)

3. **User Interface** (Presentation Layer)
   - Streamlit web application

[Detailed architecture in docs/architecture.md]

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (optional)
- **Required API Keys** (for real data integration):
  - **Anthropic API key** - Get from [Anthropic Console](https://console.anthropic.com/) (for Claude AI)
  - **RapidAPI key** - Get from [Real-Time Zillow Data API](https://rapidapi.com/marketplace/api/real-time-zillow-data) (for real Zillow property data)

### Installation

**🌐 Try it live**: [https://zillow-agent-demo.streamlit.app/](https://zillow-agent-demo.streamlit.app/)

1. Clone the repository:
```bash
git clone https://github.com/bonesdefi/zillow-agent-demo.git
cd zillow-agent-demo
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys:
# - ANTHROPIC_API_KEY: Get from https://console.anthropic.com/
# - RAPIDAPI_KEY: Get from https://rapidapi.com/marketplace/api/real-time-zillow-data
```

**Note**: This project uses **real API integrations** - mock data is not used. You must configure valid API keys to use the system.

### Streamlit Cloud Deployment

For deployment on Streamlit Cloud, configure secrets in the dashboard:
1. Go to your app settings → **Secrets**
2. Add your API keys (see `.streamlit/secrets.toml.example` for format)
3. The app automatically uses Streamlit secrets when deployed

**Live Demo**: [https://zillow-agent-demo.streamlit.app/](https://zillow-agent-demo.streamlit.app/)

5. Run the application:
```bash
streamlit run src/ui/streamlit_app.py
```

The application will open in your browser at `http://localhost:8501`

### UI Features

The Streamlit interface provides a comprehensive real estate search experience:

- **💬 Chat Interface**: Natural language conversation with the AI assistant
- **🤖 Agent Activity Sidebar**: Real-time monitoring of agent coordination and MCP server calls
- **🏘️ Property Cards**: Beautiful cards displaying property images, details, and key metrics
- **📊 AI Analysis**: Expandable sections showing:
  - Pros and cons analysis
  - Neighborhood statistics and demographics
  - School ratings with distances
  - Market trends and price history
  - Comparable sales data
- **🔍 Search Criteria Display**: Transparent view of extracted search parameters
- **📝 Conversation History**: Persistent chat history across sessions

### Docker Deployment

```bash
docker-compose up --build
```

The application will be available at `http://localhost:8501`

## 📋 Features

- ✅ **Multi-agent orchestration with LangGraph** - Complete workflow implementation
- ✅ **Custom MCP protocol implementation** - Three production-ready MCP servers
- ✅ **Real property data integration** - Live Zillow API integration via RapidAPI
- ✅ **Intelligent search agent** - Natural language intent parsing and property search
- ✅ **Market analysis agent** - Neighborhood stats, school ratings, market trends
- ✅ **Advisor agent** - Property scoring, recommendations, and explanations
- ✅ **Conversation memory and context** - User preferences and history tracking
- ✅ **Production-ready error handling** - Comprehensive error handling and logging
- ✅ **Comprehensive testing** - 96 tests with 80%+ code coverage

## 🌐 Live Demo

**Try the application live**: [https://zillow-agent-demo.streamlit.app/](https://zillow-agent-demo.streamlit.app/)

The live demo showcases all features including:
- Real-time property search with natural language queries
- AI-powered property analysis and recommendations
- Market trends and neighborhood statistics
- School ratings and comparable sales data
- Interactive chat interface with agent activity monitoring

## 📚 Documentation

- [Architecture Overview](docs/architecture.md)
- [MCP Servers Guide](docs/mcp-servers.md)
- [Agent System](docs/agents.md)
- [API Documentation](docs/api-documentation.md)
- [Deployment Guide](docs/deployment.md)

## 🧪 Testing

Run the test suite:
```bash
# Set API key for testing (agents require it for initialization)
export ANTHROPIC_API_KEY=test_key

# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
```

**Current Test Status:**
- ✅ **96 tests** passing
- ✅ **80%+ code coverage**
- ✅ All MCP servers tested
- ✅ All agents tested
- ✅ End-to-end workflow tests passing

View coverage report:
```bash
open htmlcov/index.html
```

## 🐳 Docker Deployment

The project includes Docker configuration for easy deployment:

```bash
# Build and start all services
docker-compose up --build

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 🛠️ Technology Stack

- **Language**: Python 3.11+
- **Agent Framework**: LangChain + LangGraph
- **LLM Provider**: Anthropic Claude (Claude 3.5 Sonnet)
- **MCP Implementation**: FastMCP
- **Data Sources**: Zillow API (via RapidAPI)
- **UI Framework**: Streamlit
- **Testing**: pytest with coverage
- **Type Checking**: mypy (strict mode)
- **Linting**: ruff
- **Containerization**: Docker + docker-compose

## 📄 License

MIT License

## 👤 Author

Michael P. - AI Agent Systems Engineer

- GitHub: [@bonesdefi](https://github.com/bonesdefi)
- Email: bonesdefi@gmail.com

---

**Note**: This is a production-ready system showcasing **real API integrations**:
- Real Zillow property data via RapidAPI
- Real AI capabilities using Anthropic Claude
- Production-ready error handling and data parsing
- Comprehensive testing and documentation

Property data is sourced from Zillow's public API. All code follows production best practices.

