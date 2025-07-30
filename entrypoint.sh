#!/usr/bin/env sh
set -e

# Dispatch based on first argument: "export" or "import"
case "$1" in
  export)
    shift
    exec python src/export.py "$@" ;;
  import)
    shift
    exec python src/import.py "$@" ;;
  *)
    echo "Usage: $0 {export|import} [args]" >&2
    exit 1 ;;
esac
