# Start with a lightweight Python base image
FROM python:3.8-slim

# Install Graphviz system package
RUN apt-get update && apt-get install -y graphviz

# Copy your application code into the container
COPY . /app

# Set the working directory
WORKDIR /app

# Install Python dependencies from requirements.txt
RUN pip install -r requirements.txt gunicorn eventlet

# Expose the port your app runs on
EXPOSE 5000

# Command to run your application with Gunicorn instead of the development server
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "app:app"]
