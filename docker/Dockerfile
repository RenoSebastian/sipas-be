# Dockerfile for GEOSIPAS Backend [docker/Dockerfile]
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_CREATE=false

# Set working directory
WORKDIR /app

# Install system dependencies for GIS and database libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry

# Copy project specification files
COPY pyproject.toml poetry.lock /app/

# Install python dependencies
RUN poetry install --no-root --no-directory

# Copy the application source code
COPY src /app/src
COPY alembic /app/alembic
COPY alembic.ini /app/

# Expose port
EXPOSE 8000

# Default command to run the API
CMD ["uvicorn", "src.infrastructure.http.main:app", "--host", "0.0.0.0", "--port", "8000"]
