FROM python:3.11-slim

# Install system dependencies including Tesseract OCR with Hebrew support and fonts
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-heb \
    fonts-dejavu \
    fonts-liberation \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Create directories for input and output
RUN mkdir -p input_reports output_reports

# Set default command
CMD ["python", "main.py"]

