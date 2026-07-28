#!/bin/bash
# Phase 3 본 실행 — 조건 A/B를 병렬로, 각 3판 순차.
# 재개 가능: 각 스크립트가 기존 jsonl의 완료분을 스킵한다.
set -u
cd "$(dirname "$0")/.." || exit 1

run_cond() {
  local cond=$1
  for r in run1 run2 run3; do
    .venv/bin/python scripts/phase3_run_judge.py "$cond" "$r" || {
      echo "FAILED $cond/$r"; return 1; }
  done
  echo "COND $cond COMPLETE"
}

run_cond A &
pid_a=$!
run_cond B &
pid_b=$!

wait $pid_a; rc_a=$?
wait $pid_b; rc_b=$?
echo "EXIT A=$rc_a B=$rc_b"
[ $rc_a -eq 0 ] && [ $rc_b -eq 0 ] && echo "PHASE3 RUN COMPLETE"
