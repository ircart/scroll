#!/bin/sh
# Scroll IRC Art Bot - Developed by acidvegas in Python (https://git.supernets.org/acidvegas/scroll)
# scroll/setup.sh

# Builds the patched img2irc used by .ascii img & installs it in ~/.cargo/bin

set -e

REPO='https://github.com/waveplate/img2irc'
COMMIT='ec62c7f168a3da1ca1aec2676ec27b825e731bd0'
PATCH="$(cd "$(dirname "$0")" && pwd)/img2irc.patch"
SRC="${1:-$HOME/src/img2irc}"

[ -f "$PATCH" ] || { echo "missing $PATCH"; exit 1; }

if ! command -v cargo >/dev/null && [ -f "$HOME/.cargo/env" ]; then
	# shellcheck source=/dev/null
	. "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null; then
	echo 'missing rust toolchain (curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | sh)'
	exit 1
fi

if [ -d "$SRC/.git" ]; then
	git -C "$SRC" fetch -q origin
else
	git clone -q "$REPO" "$SRC"
fi

git -C "$SRC" checkout -q "$COMMIT"
git -C "$SRC" checkout -q .
git -C "$SRC" apply "$PATCH"

cd "$SRC"
cargo generate-lockfile
if command -v cargo-audit >/dev/null; then
	cargo audit || echo 'cargo audit reported warnings'
else
	echo 'skipping cargo audit (cargo install cargo-audit)'
fi
cargo install --path . --locked

echo "img2irc installed to $(command -v img2irc)"
