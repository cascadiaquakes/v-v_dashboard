FROM python:3.12-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip
RUN pip install --requirement requirements.txt
COPY . .
EXPOSE 8050
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8050", "app_prod:server"]
