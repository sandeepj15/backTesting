FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
  build-essential \
  curl \
  software-properties-common \
  git \
  && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install TA-Lib-Precompiled

# Copy application files
COPY . .

# Expose the port Streamlit will run on
EXPOSE 8502

# Command to run the Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port", "8502", "--server.address", "0.0.0.0"]
