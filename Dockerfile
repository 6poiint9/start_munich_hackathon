FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY soony_tower ./soony_tower

# The portal data is not in the image. The server downloads it at start
# (SYNC_EVERY) with the team token from the environment.
ENV SYNC_EVERY=300 DOC_READS_PER_SYNC=3 PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn soony_tower.api:app --host 0.0.0.0 --port ${PORT}"]
