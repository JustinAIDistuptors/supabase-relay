FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the relay implementation
COPY relay.py .

# Set environment variables
ENV PORT=8080
ENV LOG_LEVEL=debug
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=supabase
ENV SUPABASE_PATH=/sss
ENV UPSTREAM_URL=https://supabase-mcp-snowy-snow-3355.fly.dev

# Expose the port
EXPOSE 8080

# Run the relay server
CMD ["python", "-m", "uvicorn", "relay:app", "--host", "0.0.0.0", "--port", "8080"]
