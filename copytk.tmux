#!/usr/bin/env bash
CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

tmux bind-key -T copytk s run-shell -b "python3 $CURRENT_DIR/copytk.py easymotion-search --search-nkeys 1"
tmux bind-key -T copytk S run-shell -b "python3 $CURRENT_DIR/copytk.py easymotion-search --search-nkeys 2"
tmux bind-key -T copytk k run-shell -b "python3 $CURRENT_DIR/copytk.py easymotion-lines --search-direction backward"
tmux bind-key -T copytk j run-shell -b "python3 $CURRENT_DIR/copytk.py easymotion-lines --search-direction forward"
tmux bind-key -T copytk n run-shell -b "python3 $CURRENT_DIR/copytk.py easymotion-lines"

tmux bind-key -T copy-mode-vi s run-shell -b "python3 $CURRENT_DIR/copytk.py easymotion-search --search-nkeys 1"
tmux bind-key -T copy-mode s run-shell -b "python3 $CURRENT_DIR/copytk.py easymotion-search --search-nkeys 1"

tmux bind-key -T copy-mode-vi S switch-client -T copytk
tmux bind-key -T copy-mode S switch-client -T copytk

