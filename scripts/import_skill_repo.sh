#!/usr/bin/env bash
# One-click import of a skill library from a git repo as submodule.
# Usage: ./scripts/import_skill_repo.sh <repo_url> [source_name]
# Example: ./scripts/import_skill_repo.sh git@github.com:Orchestra-Research/AI-Research-SKILLs.git
# Example: ./scripts/import_skill_repo.sh git@github.com:anthropics/skills.git anthropics

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ASSIGNABLE_DIR="$BACKEND_ROOT/skills/assignable_skills"
SUBMODULES_DIR="$ASSIGNABLE_DIR/_submodules"
META_FILE="$ASSIGNABLE_DIR/meta.json"

REPO_URL="${1:?Usage: $0 <repo_url> [source_name]}"
SOURCE_NAME="${2:-}"

# Derive source name from repo URL if not provided
# git@github.com:Orchestra-Research/AI-Research-SKILLs.git -> ai-research-skills
# https://github.com/Orchestra-Research/AI-Research-SKILLs -> ai-research-skills
if [ -z "$SOURCE_NAME" ]; then
  BASENAME=$(basename "$REPO_URL" .git)
  SOURCE_NAME=$(echo "$BASENAME" | tr '[:upper:]' '[:lower:]' | sed 's/[-_]skills$//' | sed 's/[-_]skill$//')
  # Ensure we have a clean id
  SOURCE_NAME=$(echo "$SOURCE_NAME" | tr -cd 'a-z0-9-' | sed 's/^-//')
  [ -z "$SOURCE_NAME" ] && SOURCE_NAME="imported"
fi

echo "Importing skill repo: $REPO_URL"
echo "Source name: $SOURCE_NAME"
echo ""

# 1. Ensure _submodules dir exists
mkdir -p "$SUBMODULES_DIR"
SUBMODULE_PATH="$SUBMODULES_DIR/$SOURCE_NAME"

# 2. Add or update submodule
if [ -d "$SUBMODULE_PATH/.git" ]; then
  echo "Submodule already exists. Updating..."
  (cd "$SUBMODULE_PATH" && git fetch origin && git checkout main 2>/dev/null || git checkout master 2>/dev/null || true && git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || git pull)
else
  echo "Adding submodule..."
  git -C "$BACKEND_ROOT" submodule add --force "$REPO_URL" "skills/assignable_skills/_submodules/$SOURCE_NAME" 2>/dev/null || {
    # If not in a git repo or submodule add fails, clone instead
    if [ ! -d "$SUBMODULE_PATH" ]; then
      git clone --depth 1 "$REPO_URL" "$SUBMODULE_PATH"
    fi
  }
fi

# 3. Run Python script to scan and update meta
python3 "$SCRIPT_DIR/import_skill_repo.py" "$SOURCE_NAME" "$SUBMODULES_DIR" "$ASSIGNABLE_DIR" "$META_FILE"

echo ""
echo "Done. Skills imported under source: $SOURCE_NAME"
echo "Restart backend to see new skills."
