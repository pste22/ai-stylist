#!/usr/bin/env bash
# Ship a branch to production (https://ai-stylist.fly.dev).
#
# Usage:  ./ship.sh [branch]        # defaults to the current branch
#         ./ship.sh --dry-run       # run the preflight checks and stop
#
# Pushing to main is what triggers the Fly deploy (.github/workflows/deploy.yml).
# This script wraps that with the parts that are easy to skip by hand: it refuses
# to ship a broken build, merges to main, then waits and confirms the commit it
# pushed is the commit actually answering in production.

set -euo pipefail

PROD_URL="${PROD_URL:-https://ai-stylist.fly.dev}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
REPO=$(cd "$(dirname "$0")" && pwd)
cd "$REPO"

DRY_RUN=0
BRANCH=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *)  BRANCH="$arg" ;;
  esac
done
[ -n "$BRANCH" ] || BRANCH=$(git rev-parse --abbrev-ref HEAD)

step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
die()  { printf '\n\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# ── Preflight ─────────────────────────────────────────────────────────────────
step "Preflight"

[ "$BRANCH" != "$MAIN_BRANCH" ] || die "Already on $MAIN_BRANCH. Ship from a feature branch."
ok "branch: $BRANCH"

if [ -n "$(git status --porcelain)" ]; then
  git status --short
  die "Working tree is dirty. Commit or stash first — shipping uncommitted work is how you lose it."
fi
ok "working tree clean"

git fetch origin "$MAIN_BRANCH" "$BRANCH" --quiet 2>/dev/null || git fetch origin --quiet
if ! git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
  die "origin/$BRANCH does not exist. Push the branch first: git push -u origin $BRANCH"
fi
if [ "$(git rev-parse "$BRANCH")" != "$(git rev-parse "origin/$BRANCH")" ]; then
  die "$BRANCH differs from origin/$BRANCH. Push (or pull) so local and remote agree."
fi
ok "branch is pushed and in sync"

AHEAD=$(git rev-list --count "origin/$MAIN_BRANCH..$BRANCH")
[ "$AHEAD" -gt 0 ] || die "Nothing to ship — $BRANCH has no commits that $MAIN_BRANCH lacks."
ok "$AHEAD commit(s) to ship"

if ! git merge-tree "$(git merge-base "$BRANCH" "origin/$MAIN_BRANCH")" "$BRANCH" "origin/$MAIN_BRANCH" \
     | grep -q '^<<<<<<<'; then
  ok "merges cleanly into $MAIN_BRANCH"
else
  die "Merge conflict with $MAIN_BRANCH. Rebase first: git rebase origin/$MAIN_BRANCH"
fi

# ── Build gate ────────────────────────────────────────────────────────────────
# The frontend build runs inside the Docker image, so a broken build fails the
# deploy several minutes in. Catching it here costs seconds.
step "Build check"
if [ -d web/node_modules ]; then
  (cd web && npm run build --silent >/tmp/ship-build.log 2>&1) \
    || { tail -20 /tmp/ship-build.log; die "Frontend build failed — not shipping."; }
  ok "frontend builds"
else
  echo "  ⚠ web/node_modules missing; skipping build check (run: cd web && npm install)"
fi

PY=$(command -v python3 || command -v python || true)
if [ -n "$PY" ]; then
  "$PY" -m compileall -q prototype >/tmp/ship-py.log 2>&1 \
    || { tail -20 /tmp/ship-py.log; die "Python syntax error — not shipping."; }
  ok "backend compiles"
fi

if [ "$DRY_RUN" = "1" ]; then
  printf '\n\033[1mDry run: preflight passed, nothing shipped.\033[0m\n'
  exit 0
fi

# ── Merge and push ────────────────────────────────────────────────────────────
step "Merging $BRANCH → $MAIN_BRANCH"
PREV_SHA=$(git rev-parse "origin/$MAIN_BRANCH")
SUBJECT=$(git log -1 --format=%s "$BRANCH")

git checkout "$MAIN_BRANCH" --quiet
git pull --ff-only origin "$MAIN_BRANCH" --quiet
git merge --no-ff "$BRANCH" -m "Merge $BRANCH: $SUBJECT" --quiet
SHA=$(git rev-parse HEAD)

if ! git push origin "$MAIN_BRANCH" --quiet; then
  git reset --hard "$PREV_SHA" --quiet
  git checkout "$BRANCH" --quiet
  die "Push rejected. Local $MAIN_BRANCH was rolled back; nothing was deployed."
fi
ok "pushed ${SHA:0:7} to $MAIN_BRANCH"
git checkout "$BRANCH" --quiet

# ── Watch the deploy ──────────────────────────────────────────────────────────
step "Deploying to $PROD_URL"
echo "  GitHub Actions builds the image and runs flyctl deploy; usually ~1-2 min."

if command -v gh >/dev/null 2>&1; then
  sleep 10
  RUN_ID=$(gh run list --workflow=deploy.yml --branch "$MAIN_BRANCH" --limit 5 \
             --json databaseId,headSha -q \
             "[.[] | select(.headSha==\"$SHA\")][0].databaseId" 2>/dev/null || true)
  if [ -n "$RUN_ID" ] && [ "$RUN_ID" != "null" ]; then
    echo "  run: $(gh run view "$RUN_ID" --json url -q .url 2>/dev/null)"
    gh run watch "$RUN_ID" --exit-status --compact >/dev/null 2>&1 \
      && ok "workflow succeeded" \
      || die "Deploy workflow failed. Logs: gh run view $RUN_ID --log-failed"
  else
    echo "  ⚠ couldn't match a workflow run; falling back to polling $PROD_URL"
  fi
fi

# ── Verify what's actually live ───────────────────────────────────────────────
# A green workflow only means flyctl exited 0. This confirms the running
# container reports the commit we just pushed.
step "Verifying production"
DEADLINE=$(( $(date +%s) + 300 ))
LIVE=""
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  BODY=$(curl -fsS --max-time 20 "$PROD_URL/health" 2>/dev/null || true)
  LIVE=$(printf '%s' "$BODY" | sed -n 's/.*"commit"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  if [ "$LIVE" = "$SHA" ]; then
    ok "live commit matches ${SHA:0:7}"
    printf '  %s\n' "$BODY"
    break
  fi
  sleep 10
done

if [ "$LIVE" != "$SHA" ]; then
  # The machine suspends when idle, so the first request after a deploy can 502
  # while Python resumes. Treat a healthy-but-stale response as inconclusive.
  if [ -n "$LIVE" ]; then
    die "Production still reports commit ${LIVE:0:7}, expected ${SHA:0:7}. Check: gh run list --workflow=deploy.yml"
  fi
  die "No healthy response from $PROD_URL/health within 5 min. Check: gh run list --workflow=deploy.yml"
fi

STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$PROD_URL/")
[ "$STATUS" = "200" ] || die "App returned HTTP $STATUS"
ok "app serving 200"

printf '\n\033[1;32m✦ Shipped.\033[0m %s is live at %s\n\n' "${SHA:0:7}" "$PROD_URL"
