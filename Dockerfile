# Use the official Python image
FROM python:3.8-slim

# Install Graphviz system package
RUN apt-get update && apt-get install -y graphviz

# Copy requirements first for better caching
COPY requirements.txt /app/
WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn flask-socketio

# Copy the rest of the application
COPY . /app

# Expose port
EXPOSE 5000

# Run with the basic Flask server but allow unsafe Werkzeug
CMD ["python", "-c", "from app import app, socketio; socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)"]
