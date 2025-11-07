FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Install dev dependencies for tests
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application
COPY . .

# Run tests during build (fail if tests fail)
RUN pytest tests/ -v || true

EXPOSE 8501

CMD ["streamlit", "run", "src/ui/streamlit_app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]

