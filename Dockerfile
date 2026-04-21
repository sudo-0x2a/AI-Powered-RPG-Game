# 1. Base Image: Start with a lightweight Python version
FROM python:3.12-slim

# 2. Install Node.js and npm (required for frontend dependencies)
# We clean up apt lists to keep the image small
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# 3. Work Directory: Set the folder inside the container where we will work
WORKDIR /app

# 4. Python Dependencies: Copy requirements first (for efficient caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Source: Copy all your project files into the container
COPY . .

# 6. Frontend Dependencies: Install Phaser
WORKDIR /app/phaser_JS
RUN npm install

# 7. Reset Work Directory to root for the CMD
WORKDIR /app

# 8. Port: Tell Docker this container listens on port 8000
EXPOSE 8000

# 9. Command: What to run when the container starts
CMD ["python", "server.py"]
