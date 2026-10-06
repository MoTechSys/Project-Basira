FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BOT_HEARTBEAT_FILE=/tmp/basira-bot.heartbeat
WORKDIR /app
COPY pyproject.toml ./
COPY bot/ bot/
RUN pip install --no-cache-dir . && useradd -r -u 10001 bot
USER bot
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import time,sys;sys.exit(0 if time.time()-int(open('/tmp/basira-bot.heartbeat').read())<90 else 1)"
CMD ["python", "-m", "bot.main"]
