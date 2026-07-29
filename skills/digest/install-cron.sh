#!/usr/bin/env bash
# Register / refresh OpenClaw cron jobs for gotit plan digests (+ optional news).
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

# Prefer gotit digest_prefs when API is up; else file config.
PREFS_JSON="$(
  uv run --directory "$REPO_ROOT" python - <<'PY' 2>/dev/null || true
import json
try:
    import asyncio
    from gotit.db.ops import get_digest_prefs
    from gotit.db.runtime import ensure_db
    from gotit.db.session import session_scope

    async def _run():
        await ensure_db()
        async with session_scope() as session:
            return (await get_digest_prefs(session)).model_dump(mode="json")

    print(json.dumps(asyncio.run(_run()), ensure_ascii=False))
except Exception:
    raise SystemExit(1)
PY
)"

if [[ -n "${PREFS_JSON}" ]]; then
  MORNING_CRON="$(printf '%s' "$PREFS_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('morning_cron') or '0 8 * * *')")"
  EVENING_CRON="$(printf '%s' "$PREFS_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('evening_cron') or '0 21 * * *')")"
  TZ_NAME="$(printf '%s' "$PREFS_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('timezone') or 'Asia/Shanghai')")"
  NEWS_ENABLED="$(printf '%s' "$PREFS_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print('1' if d.get('news_enabled') else '0')")"
  NEWS_CRON="$(printf '%s' "$PREFS_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('news_cron') or '0 12 * * *')")"
else
  MORNING_CRON="$(python3 -c "import json; print(json.load(open(r'$CONFIG')).get('morning_cron','0 8 * * *'))")"
  EVENING_CRON="$(python3 -c "import json; print(json.load(open(r'$CONFIG')).get('evening_cron','0 21 * * *'))")"
  TZ_NAME="$(python3 -c "import json; print(json.load(open(r'$CONFIG')).get('timezone','Asia/Shanghai'))")"
  NEWS_ENABLED="$(python3 -c "import json; print('1' if json.load(open(r'$CONFIG')).get('news_enabled') else '0')")"
  NEWS_CRON="$(python3 -c "import json; print(json.load(open(r'$CONFIG')).get('news_cron') or '0 12 * * *')")"
fi

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

CMD_MORNING="uv run --directory ${REPO_ROOT} python ${SKILL_DIR}/fetch_digest.py morning"
CMD_EVENING="uv run --directory ${REPO_ROOT} python ${SKILL_DIR}/fetch_digest.py evening"
CMD_NEWS="uv run --directory ${REPO_ROOT} python ${SKILL_DIR}/fetch_digest.py news"

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
    if name in ("gotit-morning-digest","gotit-evening-digest","gotit-news-digest"):
        jid=j.get("id") or j.get("jobId") or ""
        if jid:
            print(jid)
')"

while IFS= read -r id; do
  [[ -z "$id" ]] && continue
  echo "Removing old job $id"
  openclaw cron rm "$id" || true
done <<< "$OLD_IDS"

echo "Adding morning plan ($MORNING_CRON $TZ_NAME) → $WEIXIN_TO"
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
  --description "Gotit morning: today's learning plan (Asia/Shanghai)"

echo "Adding evening tomorrow-plan ($EVENING_CRON $TZ_NAME) → $WEIXIN_TO"
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
  --description "Gotit evening: tomorrow plan ask (no news / no due mix)"

if [[ "$NEWS_ENABLED" == "1" ]]; then
  echo "Adding optional news ($NEWS_CRON $TZ_NAME) → $WEIXIN_TO"
  openclaw cron add \
    --name "gotit-news-digest" \
    --cron "$NEWS_CRON" \
    --tz "$TZ_NAME" \
    --exact \
    --command "$CMD_NEWS" \
    --command-cwd "$REPO_ROOT" \
    --announce \
    --channel "$CHANNEL" \
    "${ACCOUNT_ARGS[@]}" \
    --to "$WEIXIN_TO" \
    --timeout-seconds 120 \
    --description "Gotit optional AI/YouTube RSS news (separate from plan)"
else
  echo "News cron skipped (news_enabled=false). Enable in Settings「计划推送」then re-sync."
fi

echo
echo "Done. Manual run:"
echo "  openclaw cron list"
echo "  openclaw cron run <job-id> --wait --wait-timeout 3m"
openclaw cron list
