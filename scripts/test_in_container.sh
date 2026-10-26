#!/bin/sh
# Run the unit tests inside the API image, where LlamaIndex is installed.
#
# The image does not contain the tests. This starts a one-off container from
# that image, installs the dev requirements if pytest is missing, and mounts
# the tests in. From the repository root:
#
#   scripts/test_in_container.sh
#
# The API container can keep running. This does not use its Chroma database.
set -eu
cd "$(dirname "$0")/.."
exec docker compose run --rm --no-deps --name talkback-pytest --user root \
  --entrypoint python \
  -e HF_HUB_OFFLINE=1 \
  -e TRANSFORMERS_OFFLINE=1 \
  -e HF_DATASETS_OFFLINE=1 \
  -e PYTHONPATH=/app \
  -v "$PWD/app/tests:/opt/talkback/app/tests:ro" \
  -v "$PWD/scripts:/opt/talkback/scripts:ro" \
  -v "$PWD/tests/eval:/opt/talkback/tests/eval:ro" \
  -v "$PWD/requirements-dev.txt:/opt/requirements-dev.txt:ro" \
  rag-api -c '
import importlib.util
import subprocess
import sys

if importlib.util.find_spec("pytest") is None:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-r", "/opt/requirements-dev.txt"]
    )
raise SystemExit(
    subprocess.call(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "/opt/talkback/app/tests"]
    )
)
'