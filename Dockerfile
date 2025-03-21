# Start with a lightweight Python base image
FROM python:3.8-slim

# Install Graphviz system package
RUN apt-get update && apt-get install -y graphviz

# Copy your application code into the container
COPY . /app

# Set the working directory
WORKDIR /app

# Install Python dependencies from requirements.txt
RUN pip install -r requirements.txt

# Command to run your application (adjust 'my_app.py' to your script's name)
CMD ["python", "app.py"]