# Use an official Python 3.11 image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY main.py .

# Set the command to run the bot
CMD ["python", "main.py"]