#!/usr/bin/env bash
#
# Build the distributable bundle `rename-scientific-pdf.skill` from the
# canonical sources (SKILL.md + scripts/). This is the single source of truth:
# the bundle is never committed — it is produced here and attached to releases.
#
# Structure (matches what Claude Code / Cowork expects):
#   scientific-pdf Skill/
#     scientific-pdf.skill        <- nested zip of SKILL.md + scripts
#     SKILL.md
#     scripts/process_pdf.py
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/rename-scientific-pdf.skill"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

DIR="$WORK/scientific-pdf Skill"
mkdir -p "$DIR/scripts"
cp "$ROOT/SKILL.md" "$DIR/SKILL.md"
cp "$ROOT/scripts/process_pdf.py" "$DIR/scripts/process_pdf.py"

cd "$WORK"

# Inner skill zip (SKILL.md + scripts only)
zip -q -X inner.zip \
  "scientific-pdf Skill/SKILL.md" \
  "scientific-pdf Skill/scripts/process_pdf.py"
mv inner.zip "scientific-pdf Skill/scientific-pdf.skill"

# Outer bundle: nested .skill first, then the loose files
rm -f "$OUT"
zip -q -X "$OUT" \
  "scientific-pdf Skill/scientific-pdf.skill" \
  "scientific-pdf Skill/SKILL.md" \
  "scientific-pdf Skill/scripts/process_pdf.py"

echo "Built $OUT"
unzip -l "$OUT"
