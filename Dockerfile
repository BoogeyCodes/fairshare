FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FAIRSHARE_HOST=0.0.0.0 \
    FAIRSHARE_PORT=8000 \
    FAIRSHARE_DATABASE_URL=sqlite:////data/fairshare.db

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Run as a non-root user that owns the SQLite data directory.
RUN useradd --create-home app && mkdir -p /data && chown app:app /data
VOLUME /data
EXPOSE 8000
USER app

CMD ["python", "-m", "fairshare"]
