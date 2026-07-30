#!/bin/bash
# Diffs the Harness entities in .harness/ against what is actually live.
#
# The pipeline, template, and triggers are all storeType INLINE: Harness keeps the
# authoritative YAML in its own database, and the files under .harness/ are
# hand-maintained copies with no link to it. Nothing warns you when they disagree,
# in either direction:
#
#   - Edit and commit a file here      -> the live pipeline does not change.
#   - Edit in the Harness UI           -> this copy silently goes stale.
#
# Both are bad, but the first is worse: the files sit at the exact path a git-synced
# Harness setup uses, so they look authoritative. Run this to make drift loud.
#
# Usage:  ./scripts/check-pipeline-drift.sh          # report drift, exit 1 if any
#         ./scripts/check-pipeline-drift.sh --pull   # overwrite local copies from live
#
# Requires HARNESS_PAT. Read-only against the Harness API (GETs only), even with --pull.

set -uo pipefail

ACCOUNT="${HARNESS_ACCOUNT_ID:-EeRjnXTnS4GrLG5VNNJZUw}"
ORG="${HARNESS_ORG:-sandbox}"
PROJECT="${HARNESS_PROJECT:-harness_demo_seanc}"
PIPELINE="${HARNESS_PIPELINE:-harness_demo}"
BASE="https://app.harness.io"

PULL=0
[ "${1:-}" = "--pull" ] && PULL=1

if [ -z "${HARNESS_PAT:-}" ]; then
    echo "ERROR: HARNESS_PAT is not set." >&2
    exit 2
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

SCOPE="accountIdentifier=$ACCOUNT&orgIdentifier=$ORG&projectIdentifier=$PROJECT"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

DRIFTED=()
MISSING=()
CHECKED=0

# Pulls one entity's live YAML out of the API's JSON envelope. Different endpoints
# nest it differently, hence the jq-style path argument.
fetch() {
    local url="$1" path="$2" out="$3"
    curl -sf --max-time 30 "$url" -H "x-api-key: $HARNESS_PAT" \
        | PYPATH="$path" python3 -c '
import json, os, sys
node = json.load(sys.stdin)
for key in os.environ["PYPATH"].split("."):
    node = (node or {}).get(key)
if not node:
    sys.exit(1)
sys.stdout.write(node)
' > "$out" 2>/dev/null
}

compare() {
    local label="$1" local_file="$2" live_file="$3"

    if [ ! -s "$live_file" ]; then
        echo "  ?? $label — could not fetch live YAML (does it still exist?)"
        MISSING+=("$label")
        return
    fi

    CHECKED=$((CHECKED + 1))

    if [ ! -f "$local_file" ]; then
        echo "  ++ $label — live entity has no copy at $local_file"
        MISSING+=("$label")
        [ "$PULL" = 1 ] && mkdir -p "$(dirname "$local_file")" && cp "$live_file" "$local_file"
        return
    fi

    # Ignore trailing whitespace only; any real difference counts.
    if diff -q <(sed -e 's/[[:space:]]*$//' "$live_file") \
               <(sed -e 's/[[:space:]]*$//' "$local_file") >/dev/null; then
        echo "  ok $label"
        return
    fi

    DRIFTED+=("$label")
    if [ "$PULL" = 1 ]; then
        cp "$live_file" "$local_file"
        echo "  <- $label — pulled live version into $local_file"
    else
        echo "  !! $label — DRIFTED from live ($local_file)"
        diff -u <(sed -e 's/[[:space:]]*$//' "$local_file") \
                <(sed -e 's/[[:space:]]*$//' "$live_file") \
            --label "local/$label" --label "live/$label" | sed 's/^/       /'
    fi
}

echo "=== Harness drift check: $ORG/$PROJECT ==="
echo ""

# --- pipeline ---
fetch "$BASE/pipeline/api/pipelines/$PIPELINE?$SCOPE" \
      "data.yamlPipeline" "$TMP/pipeline.yaml"
compare "pipeline/$PIPELINE" \
        ".harness/pipelines/harness_demo_pipeline.yaml" "$TMP/pipeline.yaml"

# --- template ---
fetch "$BASE/template/api/templates/docker_build_push?$SCOPE&versionLabel=v1" \
      "data.yaml" "$TMP/template.yaml"
compare "template/docker_build_push:v1" \
        ".harness/templates/docker_build_push.yaml" "$TMP/template.yaml"

# --- triggers ---
for trigger in on_push_main on_pull_request; do
    fetch "$BASE/pipeline/api/triggers/$trigger?$SCOPE&targetIdentifier=$PIPELINE" \
          "data.yaml" "$TMP/$trigger.yaml"
    compare "trigger/$trigger" ".harness/triggers/$trigger.yaml" "$TMP/$trigger.yaml"
done

echo ""

if [ "$CHECKED" = 0 ]; then
    echo "ERROR: fetched nothing — check HARNESS_PAT and network before trusting this." >&2
    exit 2
fi

if [ ${#DRIFTED[@]} = 0 ] && [ ${#MISSING[@]} = 0 ]; then
    echo "=== In sync: $CHECKED entities match live. ==="
    exit 0
fi

if [ "$PULL" = 1 ]; then
    echo "=== Pulled ${#DRIFTED[@]} drifted entity(ies) from live. Review with git diff. ==="
    exit 0
fi

echo "=== DRIFT: ${#DRIFTED[@]} differ, ${#MISSING[@]} unresolved (of $CHECKED checked) ==="
echo ""
echo "The live entity is authoritative — these are INLINE, so committing a file here"
echo "changes nothing. To reconcile:"
echo "  live is right   ->  ./scripts/check-pipeline-drift.sh --pull   (then commit)"
echo "  local is right  ->  PUT the YAML to the Harness API, or paste it in the UI"
exit 1
