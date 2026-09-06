# Shared portable / cloud-folder env for install-and-run.sh and launch-cloud.sh.
# Sourced, not executed. Expects ROOT to be the repo root.

if [ -f "$ROOT/easy-books-portable.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/easy-books-portable.env"
  set +a
fi

_portable=0
case "${EB_PORTABLE:-}" in
  1|true|TRUE|yes|YES|on|ON) _portable=1 ;;
esac
if [ -f "$ROOT/.easy-books-portable" ]; then
  _portable=1
fi

if [ "$_portable" = "1" ]; then
  export EB_PORTABLE=1
  export EB_CLOUD_SAFE_SQLITE="${EB_CLOUD_SAFE_SQLITE:-true}"
  export EB_INSTANCE_LOCK="${EB_INSTANCE_LOCK:-true}"
  if [ -z "${EB_DATA_DIR:-}" ]; then
    if [ -n "${EB_CLOUD_DATA_DIR:-}" ]; then
      export EB_DATA_DIR="$EB_CLOUD_DATA_DIR"
    else
      export EB_DATA_DIR="$ROOT/data"
    fi
  fi
fi
unset _portable
