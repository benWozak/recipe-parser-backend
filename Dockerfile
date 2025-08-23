# Multi-stage build for HomeChef Companion Backend
# Stage 1: Build stage with all build dependencies
FROM python:3.12-slim-bookworm as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libmagic1 \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers in the virtual environment
RUN playwright install chromium --with-deps

# Stage 2: Runtime stage with minimal dependencies
FROM python:3.12-slim-bookworm

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    libmagic1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy Playwright browsers from builder stage
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Create media directories with proper permissions
RUN mkdir -p /app/media/images \
             /app/media/videos \
             /app/media/thumbnails \
             /app/media/video_thumbnails \
             /app/media/temp \
             /app/media/metadata \
             /app/media/quarantine \
             /app/logs && \
    chown -R appuser:appuser /app

# Copy application code
COPY . .

# Set ownership of application files
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=10)"

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]