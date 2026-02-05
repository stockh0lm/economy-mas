#!/usr/bin/env bash
set -euo pipefail

# Batch runner for refactoring prompts with dual-model review.
# Supports opencode via configurable commands.
#
# Usage:
#   MODEL_IMPL=devstral \
#   MODEL_REVIEW=glm-4.7 \
#   MAX_ITERS=3 \
#   RETRY_MAX=2 \
#   PROMPT_INDEX=1 \
#   DRY_RUN=0 \
#   ./tools/run_refactor_batch.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_DIR="$REPO_ROOT/doc/refactoring_prompts"
REPORT_DIR="$REPO_ROOT/doc/refactoring_reports"

MODEL_IMPL="${MODEL_IMPL:-devstral}"
MODEL_REVIEW="${MODEL_REVIEW:-glm-4.7}"
MAX_ITERS="${MAX_ITERS:-3}"
REVIEW_PASS_TOKEN="${REVIEW_PASS_TOKEN:-REVIEW_PASS}"
REVIEW_FAIL_TOKEN="${REVIEW_FAIL_TOKEN:-REVIEW_FAIL}"
TESTS_PASS_TOKEN="${TESTS_PASS_TOKEN:-TESTS_PASS}"
TESTS_FAIL_TOKEN="${TESTS_FAIL_TOKEN:-TESTS_FAIL}"
RETRY_MAX="${RETRY_MAX:-2}"
RETRY_SLEEP_SEC="${RETRY_SLEEP_SEC:-5}"
DRY_RUN="${DRY_RUN:-0}"

PROMPTS=(
  "$PROMPT_DIR/01_golden_test_fix.md"
  "$PROMPT_DIR/02_golden_test_suite.md"
  "$PROMPT_DIR/03_plot_metrics_tests.md"
  "$PROMPT_DIR/04_extract_simulation_engine.md"
  "$PROMPT_DIR/05_refactor_metrics.md"
  "$PROMPT_DIR/06_extract_household_components.md"
  "$PROMPT_DIR/07_increase_test_coverage.md"
  "$PROMPT_DIR/08_performance_optimization.md"
  "$PROMPT_DIR/09_documentation_types.md"
  "$PROMPT_DIR/10_comprehensive_regression.md"
)

PROMPT_INDEX="${PROMPT_INDEX:-}"

mkdir -p "$REPORT_DIR"

timestamp() {
  date "+%Y%m%d_%H%M%S"
}

run_cli() {
  local model="$1"
  local prompt_file="$2"
  local log_file="$3"
  local attempt=1

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "DRY_RUN: (cd $REPO_ROOT && opencode run --model $model --file $prompt_file 'Execute the attached prompt file end-to-end. If reviewer, conclude with REVIEW_PASS or REVIEW_FAIL. If implementer, conclude with TESTS_PASS or TESTS_FAIL.')" >> "$log_file"
    return 0
  fi

  while [[ $attempt -le $RETRY_MAX ]]; do
    if (cd "$REPO_ROOT" && opencode run \
      --model "$model" \
      --file "$prompt_file" \
      "Execute the attached prompt file end-to-end. If reviewer, conclude with REVIEW_PASS or REVIEW_FAIL. If implementer, conclude with TESTS_PASS or TESTS_FAIL.") >"$log_file" 2>&1; then
      return 0
    fi
    echo "opencode run failed (attempt $attempt/$RETRY_MAX)" >> "$log_file"
    attempt=$((attempt + 1))
    sleep "$RETRY_SLEEP_SEC"
  done
  return 1
}

review_prompt_header() {
  cat <<'EOF'

---

Reviewer instructions:
- Review the diff and changes against the prompt requirements.
- If all requirements are met and tests pass, end your response with: REVIEW_PASS
- If issues remain, end your response with: REVIEW_FAIL
- When failing, provide concrete fixes or a patch description for the implementer.

Reviewer must check implementer test status token. If implementer reported TESTS_FAIL or did not report TESTS_PASS, reviewer must end with REVIEW_FAIL.

EOF
}

impl_prompt_header() {
  cat <<'EOF'

---

Implementer instructions:
- Apply reviewer feedback from the last iteration.
- Re-run required verification commands.
- Summarize changes and remaining risks.
- End your response with TESTS_PASS if all required verification commands succeeded.
- End your response with TESTS_FAIL if any required verification command failed.

EOF
}

idx=0
for prompt in "${PROMPTS[@]}"; do
  idx=$((idx + 1))
  if [[ -n "$PROMPT_INDEX" && "$idx" != "$PROMPT_INDEX" ]]; then
    continue
  fi
  if [[ ! -f "$prompt" ]]; then
    echo "Missing prompt file: $prompt" >&2
    exit 1
  fi

  base_name="$(basename "$prompt" .md)"
  run_stamp="$(timestamp)"

  echo "==> Running prompt: $base_name"

  # Snapshot state
  git -C "$REPO_ROOT" status --porcelain=v1 > "$REPORT_DIR/${base_name}_${run_stamp}_status.txt"
  git -C "$REPO_ROOT" diff > "$REPORT_DIR/${base_name}_${run_stamp}_diff_before.patch"

  iter=1
  while [[ $iter -le $MAX_ITERS ]]; do
    iter_stamp="${run_stamp}_iter${iter}"
    impl_prompt="$REPORT_DIR/${base_name}_${iter_stamp}_impl_prompt.md"
    review_prompt="$REPORT_DIR/${base_name}_${iter_stamp}_review_prompt.md"

    cp "$prompt" "$impl_prompt"

    if [[ $iter -gt 1 ]]; then
      prev_iter=$((iter - 1))
      prev_stamp="${run_stamp}_iter${prev_iter}"
      if [[ -f "$REPORT_DIR/${base_name}_${prev_stamp}_review.log" ]]; then
        impl_prompt_header >> "$impl_prompt"
        tail -n 200 "$REPORT_DIR/${base_name}_${prev_stamp}_review.log" >> "$impl_prompt"
      fi
    fi

    # Implementer pass
    run_cli "$MODEL_IMPL" "$impl_prompt" "$REPORT_DIR/${base_name}_${iter_stamp}_impl.log"

    if [[ "$DRY_RUN" != "1" ]] && ! grep -q "$TESTS_PASS_TOKEN" "$REPORT_DIR/${base_name}_${iter_stamp}_impl.log"; then
      if grep -q "$TESTS_FAIL_TOKEN" "$REPORT_DIR/${base_name}_${iter_stamp}_impl.log"; then
        echo "==> Implementer reported test failure for $base_name (iter $iter)" >&2
      else
        echo "==> Implementer did not report TESTS_PASS for $base_name (iter $iter)" >&2
      fi
      exit 1
    fi

    # Reviewer pass
    cp "$prompt" "$review_prompt"
    review_prompt_header >> "$review_prompt"
    if [[ -f "$REPORT_DIR/${base_name}_${iter_stamp}_impl.log" ]]; then
      printf "\nReview this implementer log (tail):\n" >> "$review_prompt"
      tail -n 200 "$REPORT_DIR/${base_name}_${iter_stamp}_impl.log" >> "$review_prompt"
    fi
    run_cli "$MODEL_REVIEW" "$review_prompt" "$REPORT_DIR/${base_name}_${iter_stamp}_review.log"

    if grep -q "$REVIEW_PASS_TOKEN" "$REPORT_DIR/${base_name}_${iter_stamp}_review.log"; then
      echo "==> Reviewer pass for $base_name (iter $iter)"
      break
    fi

    if grep -q "$REVIEW_FAIL_TOKEN" "$REPORT_DIR/${base_name}_${iter_stamp}_review.log"; then
      echo "==> Reviewer fail for $base_name (iter $iter)"
    else
      echo "==> Reviewer did not emit pass/fail token for $base_name (iter $iter)"
    fi

    iter=$((iter + 1))
    if [[ $iter -gt $MAX_ITERS ]]; then
      echo "==> Max iterations reached for $base_name" >&2
      exit 1
    fi
  done

  # Capture diff after
  git -C "$REPO_ROOT" diff > "$REPORT_DIR/${base_name}_${run_stamp}_diff_after.patch"
  git -C "$REPO_ROOT" status --porcelain=v1 > "$REPORT_DIR/${base_name}_${run_stamp}_status_after.txt"

  echo "==> Completed prompt: $base_name"
done

echo "All prompts processed. Logs and diffs in: $REPORT_DIR"
