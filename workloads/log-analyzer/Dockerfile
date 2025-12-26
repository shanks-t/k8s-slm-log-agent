FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy service files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "log_analyzer.main:app", "--host", "0.0.0.0", "--port", "8000"]
