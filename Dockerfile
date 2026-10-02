FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EVALFORGE_DATABASE_URL=sqlite:////data/evalforge.db \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY schemas ./schemas
COPY dashboard ./dashboard
COPY examples ./examples
RUN pip install ".[rag,dashboard]" \
    && groupadd --system evalforge \
    && useradd --system --gid evalforge --create-home evalforge \
    && mkdir -p /data \
    && chown evalforge:evalforge /data \
    && chmod -R a+rX /app

USER evalforge

EXPOSE 8000
CMD ["uvicorn", "evalforge.api:app", "--host", "0.0.0.0", "--port", "8000"]
