#!/usr/bin/env bash
# Pull the three local models Omnitrix uses (~14 GB in total). Needs Ollama running (ollama.com).
set -euo pipefail
MAIN="${OMNITRIX_MODEL_MAIN:-qwen3:14b}"     # ~9 GB
FAST="${OMNITRIX_MODEL_FAST:-qwen3:4b}"      # ~3 GB
EMBED="${OMNITRIX_MODEL_EMBED:-bge-m3}"      # ~1 GB
for m in "$FAST" "$EMBED" "$MAIN"; do
  echo "==> ollama pull $m"
  ollama pull "$m"
done
ollama list
