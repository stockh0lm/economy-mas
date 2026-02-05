#!/usr/bin/env bash
set -euo pipefail

# Batch runner for refactoring prompts with dual-model review.
# Supports opencode or CLI Cline via configurable commands.
#
# Usage:
#   REFAC_CLI=opencode \
#   MODEL_IMPL=devstral \
#   MODEL_REVIEW=glm-4.7 \
#   ./tools/run_refactor_batch.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_DIR="$REPO_ROOT/doc/refactoring_prompts"
REPORT_DIR="$REPO_ROOT/doc/refactoring_reports"

REFAC_CLI="${REFAC_CLI:-opencode}"
MODEL_IMPL="${MODEL_IMPL:-devstral}"
MODEL_REVIEW="${MODEL_REVIEW:-glm-4.7}"

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

mkdir -p "$REPORT_DIR"

timestamp() {
  date "+%Y%m%d_%H%M%S"
}

run_cli() {
  local model="$1"
  local prompt_file="$2"
  local log_file="$3"

  case "$REFAC_CLI" in
    opencode)
      # Example: opencode run --model <model> --prompt-file <file> --workspace <dir>
      opencode run \
        --model "$model" \
        --prompt-file "$prompt_file" \
        --workspace "$REPO_ROOT" \
        --non-interactive \
        --log-file "$log_file"
      ;;
    cline)
      # Example: cline run --model <model> --prompt-file <file> --workspace <dir>
      cline run \
        --model "$model" \
        --prompt-file "$prompt_file" \
        --workspace "$REPO_ROOT" \
        --non-interactive \
        --log-file "$log_file"
      ;;
    *)
      echo "Unsupported REFAC_CLI: $REFAC_CLI" >&2
      exit 2
      ;;
  esac
}

for prompt in "${PROMPTS[@]}"; do
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

  # Implementer pass
  run_cli "$MODEL_IMPL" "$prompt" "$REPORT_DIR/${base_name}_${run_stamp}_impl.log"

  # Reviewer pass
  run_cli "$MODEL_REVIEW" "$prompt" "$REPORT_DIR/${base_name}_${run_stamp}_review.log"

  # Capture diff after
  git -C "$REPO_ROOT" diff > "$REPORT_DIR/${base_name}_${run_stamp}_diff_after.patch"
  git -C "$REPO_ROOT" status --porcelain=v1 > "$REPORT_DIR/${base_name}_${run_stamp}_status_after.txt"

  echo "==> Completed prompt: $base_name"
done

echo "All prompts processed. Logs and diffs in: $REPORT_DIR"
