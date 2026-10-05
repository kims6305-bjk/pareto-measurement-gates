#!/bin/bash
# Unattended: wait IC-1 → (PASS only) B1 constant fix → tests → C2 → [C0 → C1] → set judge.
# Operator delegated autonomy 2026-10-06 02:55 KST ("나 잘테니까 권한줄테니 알아서 다해봐").
# Stops (status file says why) on: IC-1 not PASS, any test failure, any HALT/non-zero step.
# prereg §5 / §15.2: C2 stopping on T3/T4 ⇒ V5 fixed ⇒ C0·C1 are NOT run.
set -uo pipefail
GATE=${GATE:-$(cd "$(dirname "$0")/.." && pwd)}
cd "$GATE"
PY=${PY:-$GATE/.venv/bin/python}
ST=scripts/mh_autopilot_status.txt
say() { echo "$(date '+%F %T') $*" | tee -a "$ST"; }
die() { say "STOP: $*"; exit 1; }

IC1_PID=${1:-}
say "start (waiting IC-1 pid ${IC1_PID:-none})"
while [ -n "$IC1_PID" ] && kill -0 "$IC1_PID" 2>/dev/null; do sleep 60; done
say "IC-1 runner exited"
V=$($PY -c "import json;print(json.load(open('scripts/mh_ic1_verdict.json'))['verdict'])" 2>/dev/null) \
  || die "no mh_ic1_verdict.json (scoring refused?) — see scripts/mh_ic1_sonnet5_measure.log"
say "IC-1 verdict = $V"
[ "$V" = PASS ] || die "IC-1 $V → ADDENDUM2: precision axis dropped, search NOT started"

# B1 — ADDENDUM2 INV-3 amendment, applied only now that IC-1 no longer imports mh_front
sed -i '' 's/^MODEL_FIXED = "claude-sonnet-4-6"/MODEL_FIXED = "claude-sonnet-5"/' scripts/mh_front.py
grep -q '^MODEL_FIXED = "claude-sonnet-5"' scripts/mh_front.py || die "B1 sed failed"
$PY -m pytest -q -p no:cacheprovider tests/test_mh_search.py >> "$ST" 2>&1 || die "tests failed after B1"
git add scripts/mh_front.py && git commit -q -m "mh_front.MODEL_FIXED → claude-sonnet-5 (ADDENDUM2 INV-3 amendment; B1). IC-1 PASS." -- scripts/mh_front.py \
  || die "B1 commit failed"
say "B1 committed $(git rev-parse --short HEAD)"

run() { say "search $1 start"; $PY scripts/mh_search.py --condition "$1" >> "scripts/mh_search_$1.log" 2>&1 \
          || die "search $1 failed — tail scripts/mh_search_$1.log"; say "search $1 done: $(tail -c 400 scripts/mh_search_$1.log | tr '\n' ' ')"; }
run C2
S=$(tail -1 scripts/mh_search_C2/rounds.jsonl | $PY -c "import json,sys;print(' '.join(json.load(sys.stdin)['stops']))")
case " $S " in *" T3 "*|*" T4 "*) die "C2 stopped on [$S] → V5 (판정 불가) fixed by prereg §15.2; C0/C1 skipped (saves 3,300 calls)";; esac
run C0
run C1
$PY scripts/mh_judge_sets.py --cond C0 scripts/mh_archive_C0.jsonl scripts/mh_front_C0.json \
  --cond C1 scripts/mh_archive_C1.jsonl scripts/mh_front_C1.json \
  --cond C2 scripts/mh_archive_C2.jsonl scripts/mh_front_C2.json \
  --ic1-verdict scripts/mh_ic1_verdict.json > scripts/mh_sets_verdict.json || die "set judge failed"
say "DONE verdict: $(tr -d '\n' < scripts/mh_sets_verdict.json | head -c 300)"
