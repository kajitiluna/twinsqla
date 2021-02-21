FROM python:3.6-alpine as builder

WORKDIR /app
RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt > requirements.txt


FROM python:3.6-alpine
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN pip install -r requirements.txt

COPY . .
