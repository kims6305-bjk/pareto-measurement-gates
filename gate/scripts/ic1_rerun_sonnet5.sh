set -euo pipefail
# IC-1 깨끗한 재실행 (부속서2) — 재개 가능. c000 → loose/strict → 채점 → front.
cd "$(dirname "$0")/.."
PY="uv run python"
$PY scripts/mh_run_candidate.py --candidate-id c000 --condition C2 --all-runs
$PY scripts/mh_objectives.py --candidate-id c000 --runs 'scripts/mh_c000_run*.jsonl' \
    --labels scripts/phase1_human_label_sheet.xlsx --out scripts/mh_c000_objectives.json
$PY scripts/mh_ic1_negative_control.py --measure
set +e
$PY scripts/mh_ic1_negative_control.py --score
echo "IC1_SCORE_RC=$?"
