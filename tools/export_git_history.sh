#!/usr/bin/env bash
# [산출물 2 증빙] Git 커밋 이력을 TXT 로 저장 (프로젝트 최상위에서 실행)
#   bash tools/export_git_history.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p reports
git log --oneline --graph --all --decorate > reports/git_commit_history.txt
git log --all --name-status --date=short --pretty=format:'%h %ad %an %s' > reports/git_change_history.txt
echo "reports/git_commit_history.txt ($(wc -l < reports/git_commit_history.txt)줄)"
echo "reports/git_change_history.txt ($(wc -l < reports/git_change_history.txt)줄)"
