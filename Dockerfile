FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastmcp>=2.0.0,<3.0.0" \
    "psycopg[binary]>=3.2,<4.0"

COPY server.py db.py client.py ./

EXPOSE 8000

CMD ["python", "server.py"]
