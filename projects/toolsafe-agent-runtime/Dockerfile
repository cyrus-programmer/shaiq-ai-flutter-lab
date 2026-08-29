FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app
COPY src ./src
COPY examples ./examples

RUN useradd --create-home --uid 10001 appuser
USER appuser

ENTRYPOINT ["python", "-m", "toolsafe.cli"]
CMD ["run", "--script", "examples/support-agent.json", "--message", "Where is order ORD-100?"]
