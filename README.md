# Real Estate AI Assistant - Portfolio Demo

A production-quality multi-agent AI system demonstrating LangGraph orchestration with custom MCP (Model Context Protocol) servers for intelligent real estate assistance.

**Built as a portfolio demonstration inspired by Zillow's Agentic AI initiative.**

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
- API Keys:
  - Anthropic API key (for Claude)
  - RapidAPI key (for Zillow data)

### Installation

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
# Edit .env with your API keys
```

5. Run the application:
```bash
streamlit run src/ui/streamlit_app.py
```

### Docker Deployment

```bash
docker-compose up --build
```

The application will be available at `http://localhost:8501`

## 📋 Features

- ✅ Multi-agent orchestration with LangGraph
- ✅ Custom MCP protocol implementation
- ✅ Real property data integration
- ✅ Conversation memory and context
- ✅ Market analysis and recommendations
- ✅ Production-ready error handling
- ✅ Comprehensive testing (80%+ coverage target)

## 📚 Documentation

- [Architecture Overview](docs/architecture.md)
- [MCP Servers Guide](docs/mcp-servers.md)
- [Agent System](docs/agents.md)
- [API Documentation](docs/api-documentation.md)
- [Deployment Guide](docs/deployment.md)

## 🧪 Testing

Run the test suite:
```bash
pytest tests/ -v --cov=src --cov-report=html
```

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

**Note**: This is a portfolio demonstration project. Property data is sourced from public APIs for educational purposes.

