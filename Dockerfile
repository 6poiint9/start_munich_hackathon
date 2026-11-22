# Backend: API and agents (`python -m lineguard run`).
FROM python:3.12-slim

# pdftotext and pdftoppm read PDF files (lineguard/tools/content.py).
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# Install the dependencies first so that a code change keeps this layer.
COPY pyproject.toml ./
RUN mkdir lineguard && touch lineguard/__init__.py \
    && pip install . && pip uninstall -y lineguard && rm -rf lineguard build

COPY lineguard ./lineguard
RUN pip install --no-deps -e .

# The customer pack and the data come in as volumes (docker-compose.yml).
VOLUME ["/app/data"]
EXPOSE 8000
CMD ["python", "-m", "lineguard", "run", "--host", "0.0.0.0", "--port", "8000"]
