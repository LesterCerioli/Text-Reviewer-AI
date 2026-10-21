FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY app/ app/
COPY templates/ templates/
COPY tests/ tests/

# Create non-root user for security
RUN useradd -m appuser
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Collect static files and run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]