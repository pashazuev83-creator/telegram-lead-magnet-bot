FROM python:3.12-slim

# Prevent .pyc files and force stdout/stderr to be unbuffered so logs show
# up immediately in `docker logs` / hosting platform log viewers.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# No EXPOSE needed: this bot uses long polling, not a webhook/HTTP server.

CMD ["python", "bot.py"]
