# Adaptive Framework - Dockerfile
# Multi-stage build for production deployment

# Build stage
FROM python:3.14-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY adaptive_framework/ ./adaptive_framework/

# Install package with all extras
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[all]"

# Runtime stage
FROM python:3.14-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    libssl3 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user
RUN groupadd -r adaptive && useradd -r -g adaptive adaptive

# Create data directory
RUN mkdir -p /home/adaptive/.adaptive_framework/extensions \
    /home/adaptive/.adaptive_framework/logs \
    /home/adaptive/.adaptive_framework/cache && \
    chown -R adaptive:adaptive /home/adaptive

USER adaptive
WORKDIR /home/adaptive

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ADAPTIVE_DATA_DIR=/home/adaptive/.adaptive_framework \
    PATH="/home/adaptive/.local/bin:${PATH}"

# Expose ports
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# Default command
CMD ["adaptive-web"]