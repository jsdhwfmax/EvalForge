FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY schemas ./schemas
COPY dashboard ./dashboard
COPY examples ./examples
RUN pip install --upgrade pip && pip install ".[rag,dashboard]"

EXPOSE 8000
CMD ["uvicorn", "evalforge.api:app", "--host", "0.0.0.0", "--port", "8000"]
