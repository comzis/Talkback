#!/bin/sh
# huggingface_hub.constants.HF_HUB_OFFLINE is set when that module is imported.
# The app imports it before apply_offline_mode() runs, so the flags have to
# exist before Python starts. OFFLINE_MODE defaults to true, matching the app.
mode=$(printf '%s' "${OFFLINE_MODE:-true}" | tr '[:upper:]' '[:lower:]')
case "$mode" in
  1|true|yes)
    export HF_HUB_OFFLINE=1
    export TRANSFORMERS_OFFLINE=1
    export HF_DATASETS_OFFLINE=1
    ;;
esac
exec "$@"
