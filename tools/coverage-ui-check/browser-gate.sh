#!/bin/sh
# Run browser.mjs against a disposable headless Chrome and the loopback preview.
# Chrome gets a temporary profile and a loopback debugging port, so it never
# touches a signed-in profile. The preview, Chrome and the profile are removed on
# every exit, including failure, interrupt and timeout.
#
# COVERAGE_CHROME            Chrome or Chromium binary (default: detected)
# COVERAGE_BROWSER_TIMEOUT   hard limit in seconds (default 600)
# COVERAGE_CHROME_NO_SANDBOX set to 1 where the OS blocks Chrome's sandbox (CI)
# COVERAGE_CAPTURE_DIR       keep screenshots and browser-checks.json here
set -eu
export PYTHONDONTWRITEBYTECODE=1

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LIMIT=${COVERAGE_BROWSER_TIMEOUT:-600}
case "$LIMIT" in '' | *[!0-9]*)
  printf 'FAIL: COVERAGE_BROWSER_TIMEOUT must be whole seconds\n' >&2
  exit 1
  ;;
esac

find_chrome() {
  if [ -n "${COVERAGE_CHROME:-}" ]; then
    printf '%s\n' "$COVERAGE_CHROME"
    return
  fi
  for app in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
    if [ -x "$app" ]; then
      printf '%s\n' "$app"
      return
    fi
  done
  for name in google-chrome google-chrome-stable chromium chromium-browser; do
    if command -v "$name" >/dev/null 2>&1; then
      command -v "$name"
      return
    fi
  done
}
CHROME=$(find_chrome)
if [ -z "$CHROME" ] || [ ! -x "$CHROME" ]; then
  printf 'FAIL: no Chrome found; set COVERAGE_CHROME to a Chrome or Chromium binary\n' >&2
  exit 1
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/coverage-browser.XXXXXX")
PROFILE="$TMP/profile"
PREVIEW_PID=
CHROME_PID=
CHECK_PID=
WATCHDOG_PID=

stop() {
  if [ -n "$1" ] && kill -0 "$1" 2>/dev/null; then
    kill -TERM "$1" 2>/dev/null || true
    wait "$1" 2>/dev/null || true
  fi
}
cleanup() {
  status=$?
  trap - EXIT HUP INT TERM
  stop "$WATCHDOG_PID"
  stop "$CHECK_PID"
  stop "$CHROME_PID"
  # Renderer and GPU helpers carry the unique profile path on their command line.
  pkill -KILL -f -- "--user-data-dir=$PROFILE" 2>/dev/null || true
  stop "$PREVIEW_PID"
  rm -rf "$TMP"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' HUP INT
trap 'exit 143' TERM

# The watchdog signals this shell; the TERM trap then runs cleanup. Its sleep
# holds no output descriptor, so a pipe reading this script never waits on it.
(
  trap 'kill "$timer" 2>/dev/null; exit 0' TERM
  sleep "$LIMIT" </dev/null >/dev/null 2>&1 &
  timer=$!
  wait "$timer"
  printf 'FAIL: browser checks exceeded %s seconds\n' "$LIMIT" >&2
  kill -TERM $$ 2>/dev/null
) &
WATCHDOG_PID=$!

free_port() {
  python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

PORT=$(free_port)
python3 "$HERE/preview.py" --port "$PORT" >"$TMP/preview.log" 2>&1 &
PREVIEW_PID=$!
URL="http://127.0.0.1:$PORT/"
tries=0
until python3 -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1)' "$URL" 2>/dev/null; do
  tries=$((tries + 1))
  if [ "$tries" -ge 50 ] || ! kill -0 "$PREVIEW_PID" 2>/dev/null; then
    cat "$TMP/preview.log" >&2
    printf 'FAIL: local preview did not start on port %s\n' "$PORT" >&2
    exit 1
  fi
  sleep 0.2
done

mkdir -p "$PROFILE"
set -- --headless=new --user-data-dir="$PROFILE" \
  --remote-debugging-address=127.0.0.1 --remote-debugging-port=0 \
  --no-first-run --no-default-browser-check --disable-background-networking \
  --disable-component-update --disable-sync --disable-extensions \
  --disable-default-apps --mute-audio --password-store=basic \
  --use-mock-keychain --lang=en-US
if [ "${COVERAGE_CHROME_NO_SANDBOX:-}" = 1 ]; then set -- "$@" --no-sandbox; fi
"$CHROME" "$@" "$URL" >"$TMP/chrome.log" 2>&1 &
CHROME_PID=$!

# Port 0 lets Chrome pick a free port; it writes the port and path here.
tries=0
until [ -n "$(sed -n 2p "$PROFILE/DevToolsActivePort" 2>/dev/null)" ]; do
  tries=$((tries + 1))
  if [ "$tries" -ge 100 ] || ! kill -0 "$CHROME_PID" 2>/dev/null; then
    tail -n 20 "$TMP/chrome.log" >&2
    printf 'FAIL: headless Chrome did not open a debugging port\n' >&2
    exit 1
  fi
  sleep 0.2
done
CDP_PORT=$(sed -n 1p "$PROFILE/DevToolsActivePort")
CDP_PATH=$(sed -n 2p "$PROFILE/DevToolsActivePort")
tries=0
until python3 - "http://127.0.0.1:$CDP_PORT/json/list" "$URL" 2>/dev/null <<'PY'
import json, sys, urllib.request
tabs = json.load(urllib.request.urlopen(sys.argv[1], timeout=1))
sys.exit(0 if any(t.get("type") == "page" and t.get("url", "").startswith(sys.argv[2]) for t in tabs) else 1)
PY
do
  tries=$((tries + 1))
  if [ "$tries" -ge 100 ]; then
    printf 'FAIL: headless Chrome did not open the preview\n' >&2
    exit 1
  fi
  sleep 0.2
done
printf 'browser: %s (%s)\n' "$("$CHROME" --version 2>/dev/null || printf unknown)" "$CHROME"

COVERAGE_PREVIEW_URL="$URL" \
  COVERAGE_CDP_URL="ws://127.0.0.1:$CDP_PORT$CDP_PATH" \
  COVERAGE_CAPTURE_DIR="${COVERAGE_CAPTURE_DIR:-$TMP/captures}" \
  node "$HERE/browser.mjs" >"$TMP/browser.log" 2>&1 &
CHECK_PID=$!
if wait "$CHECK_PID"; then
  CHECK_PID=
  grep -E '"history(ThrottleWarnings|Retries)"' "$TMP/browser.log" | tr -d ' ,' || true
  tail -n 1 "$TMP/browser.log"
else
  CHECK_PID=
  cat "$TMP/browser.log" >&2
  printf 'FAIL: coverage browser checks\n' >&2
  exit 1
fi
