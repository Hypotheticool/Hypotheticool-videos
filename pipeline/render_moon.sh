#!/bin/bash
cd /home/claude/b3d
for i in 0 1 2 4 5 6 7 8 3; do
  echo "scene $i start $(date +%T)" >> moon/progress.log
  python3 moon3d.py $i anim > moon/log_$i.txt 2>&1
  echo "scene $i done $(date +%T) frames $(ls moon/s$i/*.png | wc -l)" >> moon/progress.log
done
echo ALLDONE >> moon/progress.log
