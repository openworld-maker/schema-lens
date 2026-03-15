FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE /app/
COPY schema_lens /app/schema_lens

RUN pip install --no-cache-dir .

EXPOSE 8090

ENTRYPOINT ["schema-lens"]
CMD ["--help"]
