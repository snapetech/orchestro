FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir -e .

ENV ORCHESTRO_HOME=/data

EXPOSE 8765

CMD ["orchestro", "serve", "--host", "0.0.0.0", "--port", "8765"]
