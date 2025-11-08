# Deployment Guide

## Overview

The Real Estate AI Assistant can be deployed locally or in a containerized environment. The Streamlit UI provides an intuitive interface for interacting with the multi-agent system.

![Streamlit UI](images/streamlit-ui-screenshot.png)

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (for containerized deployment)
- API Keys:
  - Anthropic API key
  - RapidAPI key (for Zillow data)

## Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/bonesdefi/zillow-agent-demo.git
cd zillow-agent-demo
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Configuration

1. Copy environment template:
```bash
cp .env.example .env
```

2. Edit `.env` with your API keys:
```bash
ANTHROPIC_API_KEY=your_actual_key_here
RAPIDAPI_KEY=your_actual_key_here
```

## Local Development

### Running MCP Servers Individually

```bash
# Real Estate Server
python -m src.mcp_servers.real_estate_server

# Market Analysis Server
python -m src.mcp_servers.market_analysis_server

# User Context Server
python -m src.mcp_servers.user_context_server
```

### Running the Streamlit App

```bash
streamlit run src/ui/streamlit_app.py
```

The app will be available at `http://localhost:8501`

## Docker Deployment

### Build and Run

```bash
# Build all services
docker-compose build

# Start all services
docker-compose up

# Run in detached mode
docker-compose up -d
```

### Service URLs

- Streamlit App: `http://localhost:8501`
- Real Estate MCP Server: `http://localhost:8001`
- Market Analysis MCP Server: `http://localhost:8002`
- User Context MCP Server: `http://localhost:8003`

### Health Checks

All services include health check endpoints:

```bash
curl http://localhost:8501/_stcore/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f mcp-real-estate
```

### Stopping Services

```bash
docker-compose down
```

## Production Considerations

### Environment Variables

- Use a secrets management system (AWS Secrets Manager, HashiCorp Vault, etc.)
- Never commit `.env` files
- Use different API keys for production

### Scaling

- MCP servers can be scaled independently
- Use a load balancer for multiple instances
- Consider using Redis for shared caching

### Monitoring

- Set up application monitoring (Datadog, New Relic, etc.)
- Monitor API rate limits
- Track error rates and response times

### Security

- Use HTTPS in production
- Implement authentication if needed
- Rate limit API endpoints
- Validate all user inputs

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   - Change ports in `.env` or `docker-compose.yml`

2. **API Key Errors**
   - Verify API keys in `.env`
   - Check API key permissions

3. **MCP Server Connection Errors**
   - Ensure MCP servers are running
   - Check network connectivity
   - Verify port numbers

4. **Import Errors**
   - Ensure virtual environment is activated
   - Reinstall dependencies: `pip install -r requirements.txt`

### Debug Mode

Enable debug mode in `.env`:
```bash
ENABLE_DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

## CI/CD

The project includes GitHub Actions workflow for automated testing:

- Runs on push to main/develop branches
- Runs on pull requests
- Executes linting, type checking, and tests
- Uploads coverage reports

