FROM python:3.12-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
RUN python -m pip install --upgrade pip
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS test
COPY app ./app
COPY tests ./tests
COPY pytest.ini ./
CMD ["python", "-m", "pytest", "tests"]

FROM base AS runtime
RUN adduser --disabled-password --gecos "" appuser
COPY app ./app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
