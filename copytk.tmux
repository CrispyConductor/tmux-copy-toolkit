#!/usr/bin/env bash
CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
tmux bind-key -T prefix C-q run-shell -b "python3 $CURRENT_DIR/copytk.py easymotion-search --search-nkeys 1"


