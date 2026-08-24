FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY runtime_service /app/runtime_service
RUN chmod +x /app/runtime_service/entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    TENSURA_REPO_PATH=/srv/tensura \
    TENSURA_BRANCH=main \
    PORT=8080

VOLUME ["/srv/tensura"]
EXPOSE 8080

ENTRYPOINT ["/app/runtime_service/entrypoint.sh"]
