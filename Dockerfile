FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . .

# Expose port (HF Spaces uses 7860)
EXPOSE 7860

# Run the app
CMD ["python", "app.py"]