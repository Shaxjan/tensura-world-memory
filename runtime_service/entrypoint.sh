#!/bin/sh
set -eu

: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY owner/repo is required}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN with repository contents write access is required}"
: "${TENSURA_GITHUB_WEBHOOK_SECRET:?TENSURA_GITHUB_WEBHOOK_SECRET is required}"

REPO_PATH="${TENSURA_REPO_PATH:-/srv/tensura}"
BRANCH="${TENSURA_BRANCH:-main}"
AUTH_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"

if [ ! -d "$REPO_PATH/.git" ]; then
  rm -rf "$REPO_PATH"
  git clone --depth 50 --branch "$BRANCH" "$AUTH_URL" "$REPO_PATH"
else
  git -C "$REPO_PATH" remote set-url origin "$AUTH_URL"
  git -C "$REPO_PATH" fetch origin "$BRANCH"
  git -C "$REPO_PATH" reset --hard "origin/$BRANCH"
fi

git -C "$REPO_PATH" config user.name "tensura-runtime-service"
git -C "$REPO_PATH" config user.email "runtime-service@users.noreply.github.com"

exec python3 /app/runtime_service/app.py
