FROM python:3.12-slim

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==2.5.1

# Configure poetry to not create a virtualenv inside docker container
RUN poetry config virtualenvs.create false

# Copy pyproject.toml and poetry.lock if exists
COPY pyproject.toml /app/

# Install dependencies without dev packages
RUN poetry install --no-root --without dev

# Copy project files
COPY backend /app/backend
COPY mcp /app/mcp

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
