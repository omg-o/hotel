# Use a slim Python 3.11 image as the base.
FROM python:3.11-slim

# Install system-level dependencies required for building faiss-cpu from source.
# The `libopenmp-dev` package is not available on this Debian base image.
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libomp-dev \
    swig \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container.
WORKDIR /app

# Copy the requirements file into the working directory.
COPY requirements.txt .

# Install all Python dependencies listed in requirements.txt.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container.
COPY . .

# Expose the port that your Flask application will listen on.
EXPOSE 5000

# The command to start your application when the container is run.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
