FROM python:3.9-slim

# Install system dependencies required for pandas and numpy
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a non-root user and necessary directories
RUN useradd -m myuser && \
    mkdir -p /app/logs && \
    chown -R myuser:myuser /app

# Install core numerical libraries first
RUN pip install --no-cache-dir \
    numpy==1.24.0 \
    pandas==2.0.3 \
    scipy==1.11.3 \
    ta==0.10.2

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .
RUN chown -R myuser:myuser /app

# Switch to non-root user
USER myuser

# Command to run the application
CMD ["python", "main.py"]
