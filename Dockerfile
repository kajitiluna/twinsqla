FROM python:3.6 as builder

WORKDIR /app
RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry export --dev -f requirements.txt > requirements.txt


FROM python:3.6
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN apt update && \
    apt install -y default-mysql-client && \
    pip install -r requirements.txt

COPY . .
