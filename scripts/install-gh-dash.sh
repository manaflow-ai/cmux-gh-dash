#!/bin/sh
# Download the audited gh-dash release into this extension checkout.
# The asset ID and digest come from third_party/gh-dash.lock. No GitHub CLI
# extension is installed globally, and no mutable branch or release URL is
# followed.
set -eu

umask 077
root=$(cd -P -- "$(dirname -- "$0")/.." && pwd)
lock="$root/third_party/gh-dash.lock"

fail() {
    printf 'cmux-gh-dash: %s\n' "$1" >&2
    exit 1
}

[ -f "$lock" ] || fail "missing release lock: $lock"

case "$(uname -s):$(uname -m)" in
    Darwin:arm64) platform=darwin-arm64 ;;
    Darwin:x86_64) platform=darwin-amd64 ;;
    *) fail "unsupported platform (only macOS arm64 and x86_64 are supported)" ;;
esac

asset_id=$(awk -v platform="$platform" '$1 == "asset" && $2 == platform { print $3; exit }' "$lock")
expected_size=$(awk -v platform="$platform" '$1 == "asset" && $2 == platform { print $4; exit }' "$lock")
asset_name=$(awk -v platform="$platform" '$1 == "asset" && $2 == platform { print $5; exit }' "$lock")
expected_sha=$(awk -v platform="$platform" '$1 == "asset" && $2 == platform { print $6; exit }' "$lock")
[ -n "$asset_id" ] || fail "no locked asset for $platform"
[ -n "$expected_size" ] || fail "locked asset has no size for $platform"
[ -n "$asset_name" ] || fail "locked asset has no name for $platform"
[ -n "$expected_sha" ] || fail "locked asset has no digest for $platform"

printf '%s\n' "$asset_id" | grep -Eq '^[0-9]+$' || fail "invalid asset ID in release lock"
printf '%s\n' "$expected_size" | grep -Eq '^[0-9]+$' || fail "invalid asset size in release lock"
printf '%s\n' "$asset_name" | grep -Eq '^gh-dash_v[0-9]+\.[0-9]+\.[0-9]+_darwin-(arm64|amd64)$' || fail "invalid asset name in release lock"
printf '%s\n' "$expected_sha" | grep -Eq '^[0-9a-f]{64}$' || fail "invalid SHA-256 in release lock"

command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v gh >/dev/null 2>&1 || fail "the GitHub CLI is required"
gh auth status --hostname github.com >/dev/null 2>&1 \
    || fail "run gh auth login --hostname github.com before installing"
if [ -x /usr/bin/shasum ]; then
    hash_command=/usr/bin/shasum
elif command -v sha256sum >/dev/null 2>&1; then
    hash_command=$(command -v sha256sum)
else
    fail "shasum or sha256sum is required"
fi
[ -x /usr/bin/codesign ] || fail "codesign is required on macOS"

if [ -L "$root/bin" ] || { [ -e "$root/bin" ] && [ ! -d "$root/bin" ]; }; then
    fail "refusing to write through a non-directory bin path"
fi
mkdir -p "$root/bin"

download_dir=$(mktemp -d "$root/.gh-dash-download.XXXXXX")
cleanup() { rm -rf "$download_dir"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
download="$download_dir/$asset_name"
netrc="$download_dir/netrc"
token=$(gh auth token --hostname github.com) || fail "could not read the GitHub CLI token"
[ -n "$token" ] || fail "the GitHub CLI returned an empty token"
printf 'machine api.github.com login x-oauth-basic password %s\n' "$token" > "$netrc"
unset token
chmod 0600 "$netrc"

curl --fail --location --silent --show-error \
    --proto '=https' --tlsv1.2 --connect-timeout 30 --max-time 300 \
    --max-filesize "$expected_size" \
    --netrc-file "$netrc" --user-agent 'cmux-gh-dash/0.1' \
    --header 'Accept: application/octet-stream' \
    --output "$download" \
    "https://api.github.com/repos/dlvhdr/gh-dash/releases/assets/$asset_id"

if [ "$hash_command" = /usr/bin/shasum ]; then
    actual_sha=$($hash_command -a 256 "$download" | awk '{ print $1 }')
else
    actual_sha=$($hash_command "$download" | awk '{ print $1 }')
fi
[ "$actual_sha" = "$expected_sha" ] || fail "SHA-256 mismatch for $asset_name"
[ "$(stat -f '%z' "$download")" = "$expected_size" ] || fail "unexpected size for $asset_name"
/usr/bin/codesign --verify --strict "$download" >/dev/null 2>&1 \
    || fail "code-signature validation failed for $asset_name"

chmod 0755 "$download"
staged="$root/bin/.gh-dash.new"
[ ! -L "$staged" ] || fail "refusing to replace a symlinked staging file"
[ ! -L "$root/bin/gh-dash" ] || fail "refusing to replace a symlinked binary"
cp "$download" "$staged"
chmod 0755 "$staged"
mv -f "$staged" "$root/bin/gh-dash"
[ -x "$root/bin/gh-dash" ] || fail "installed binary is not executable"
cmp -s "$download" "$root/bin/gh-dash" || fail "installed binary changed during copy"
printf 'cmux-gh-dash: installed %s (%s)\n' "$asset_name" "$expected_sha"
