FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Seed the SQLite database at build time so it's baked into the image
RUN python init_db.py

EXPOSE 8000

CMD ["python", "server.py"]
