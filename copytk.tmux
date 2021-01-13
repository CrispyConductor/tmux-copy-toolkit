#!/usr/bin/env bash
CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
tmux bind-key -n C-y run-shell -b "python3 $CURRENT_DIR/copytk.py easymotion --search-nkeys 1"


