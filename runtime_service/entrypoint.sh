#!/bin/sh
set -eu

: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY owner/repo is required}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN with repository contents write access is required}"
: "${TENSURA_GITHUB_WEBHOOK_SECRET:?TENSURA_GITHUB_WEBHOOK_SECRET is required}"

REPO_PATH="${TENSURA_REPO_PATH:-/srv/tensura}"
BRANCH="${TENSURA_BRANCH:-main}"
REMOTE_URL="https://github.com/${GITHUB_REPOSITORY}.git"

cat >/tmp/tensura-git-askpass.sh <<'EOF'
#!/bin/sh
case "$1" in
  *Username*) printf '%s\n' 'x-access-token' ;;
  *) printf '%s\n' "$GITHUB_TOKEN" ;;
esac
EOF
chmod 700 /tmp/tensura-git-askpass.sh
export GIT_ASKPASS=/tmp/tensura-git-askpass.sh
export GIT_TERMINAL_PROMPT=0

if [ ! -d "$REPO_PATH/.git" ]; then
  rm -rf "$REPO_PATH"
  git clone --depth 50 --branch "$BRANCH" "$REMOTE_URL" "$REPO_PATH"
else
  git -C "$REPO_PATH" remote set-url origin "$REMOTE_URL"
  git -C "$REPO_PATH" fetch origin "$BRANCH"
  git -C "$REPO_PATH" reset --hard "origin/$BRANCH"
fi

git -C "$REPO_PATH" config user.name "tensura-runtime-service"
git -C "$REPO_PATH" config user.email "runtime-service@users.noreply.github.com"

exec python3 /app/runtime_service/server.py
