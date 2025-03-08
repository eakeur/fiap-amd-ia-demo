# Use an official Python image from Docker Hub
FROM python:3.12

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . .

# Install dependencies if a requirements.txt file is present
RUN pip install --no-cache-dir -r requirements.txt || true

# Set the default command to run when the container starts
CMD ["python"]
