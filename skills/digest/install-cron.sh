#!/usr/bin/env bash
# Register / refresh OpenClaw cron jobs for gotit morning + evening digests.
# Requires: Node 22+, openclaw on PATH, Gateway running, WeChat already paired.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL_DIR="$REPO_ROOT/skills/digest"
CONFIG="$SKILL_DIR/config.json"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 1; }; }
need openclaw
need python3
need uv

if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.nvm/nvm.sh"
  nvm use 22 >/dev/null 2>&1 || true
fi

MORNING_CRON="$(python3 -c "import json; print(json.load(open(r'$CONFIG')).get('morning_cron','0 8 * * *'))")"
EVENING_CRON="$(python3 -c "import json; print(json.load(open(r'$CONFIG')).get('evening_cron','0 21 * * *'))")"
TZ_NAME="$(python3 -c "import json; print(json.load(open(r'$CONFIG')).get('timezone','Asia/Shanghai'))")"

SESSIONS="${OPENCLAW_SESSIONS:-$HOME/.openclaw/agents/main/sessions/sessions.json}"

if [[ -n "${WEIXIN_TO:-}" ]]; then
  WEIXIN_ACCOUNT="${WEIXIN_ACCOUNT:-}"
else
  if [[ ! -f "$SESSIONS" ]]; then
    echo "No sessions.json at $SESSIONS — chat WeChat once, or set WEIXIN_TO=..." >&2
    exit 1
  fi
  RESOLVED="$(python3 - "$SESSIONS" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
best = None
best_ts = -1
for k, v in data.items():
    if "openclaw-weixin" not in k:
        continue
    dc = v.get("deliveryContext") or {}
    to = dc.get("to") or v.get("lastTo")
    acct = dc.get("accountId") or v.get("lastAccountId") or ""
    ts = v.get("lastInteractionAt") or v.get("updatedAt") or 0
    if to and ts >= best_ts:
        best_ts = ts
        best = (to, acct)
if not best:
    raise SystemExit("no openclaw-weixin direct session found")
print(best[0])
print(best[1])
PY
)"
  WEIXIN_TO="$(printf '%s\n' "$RESOLVED" | sed -n '1p')"
  WEIXIN_ACCOUNT="$(printf '%s\n' "$RESOLVED" | sed -n '2p')"
fi

if [[ -z "${WEIXIN_TO}" ]]; then
  echo "Could not resolve WeChat --to target" >&2
  exit 1
fi

CHANNEL="openclaw-weixin"
ACCOUNT_ARGS=()
if [[ -n "${WEIXIN_ACCOUNT}" ]]; then
  ACCOUNT_ARGS=(--account "$WEIXIN_ACCOUNT")
fi

# Single-quoted paths inside the shell string stored by cron.
CMD_MORNING="uv run --directory ${REPO_ROOT} python ${SKILL_DIR}/fetch_digest.py morning"
CMD_EVENING="uv run --directory ${REPO_ROOT} python ${SKILL_DIR}/fetch_digest.py evening"

echo "Linking skill → ~/.openclaw/workspace/skills/digest"
mkdir -p "$HOME/.openclaw/workspace/skills"
ln -sfn "$SKILL_DIR" "$HOME/.openclaw/workspace/skills/digest"

echo "Looking for existing digest jobs…"
OLD_JSON="$(openclaw cron list --all --json 2>/dev/null || echo '[]')"
OLD_IDS="$(printf '%s' "$OLD_JSON" | python3 -c '
import json,sys
raw=sys.stdin.read().strip() or "[]"
try:
    data=json.loads(raw)
except Exception:
    data=[]
jobs=data if isinstance(data,list) else (data.get("jobs") or data.get("items") or [])
for j in jobs:
    name=(j.get("name") or "")
    if name in ("gotit-morning-digest","gotit-evening-digest"):
        jid=j.get("id") or j.get("jobId") or ""
        if jid:
            print(jid)
')"

while IFS= read -r id; do
  [[ -z "$id" ]] && continue
  echo "Removing old job $id"
  openclaw cron rm "$id" || true
done <<< "$OLD_IDS"

echo "Adding morning ($MORNING_CRON $TZ_NAME) → $WEIXIN_TO"
openclaw cron add \
  --name "gotit-morning-digest" \
  --cron "$MORNING_CRON" \
  --tz "$TZ_NAME" \
  --exact \
  --command "$CMD_MORNING" \
  --command-cwd "$REPO_ROOT" \
  --announce \
  --channel "$CHANNEL" \
  "${ACCOUNT_ARGS[@]}" \
  --to "$WEIXIN_TO" \
  --timeout-seconds 120 \
  --description "Gotit morning RSS digest (Asia/Shanghai)"

echo "Adding evening ($EVENING_CRON $TZ_NAME) → $WEIXIN_TO"
openclaw cron add \
  --name "gotit-evening-digest" \
  --cron "$EVENING_CRON" \
  --tz "$TZ_NAME" \
  --exact \
  --command "$CMD_EVENING" \
  --command-cwd "$REPO_ROOT" \
  --announce \
  --channel "$CHANNEL" \
  "${ACCOUNT_ARGS[@]}" \
  --to "$WEIXIN_TO" \
  --timeout-seconds 180 \
  --description "Gotit evening digest + gotit_today due claims"

echo
echo "Done. Manual run:"
echo "  openclaw cron list"
echo "  openclaw cron run <job-id> --wait --wait-timeout 3m"
openclaw cron list
