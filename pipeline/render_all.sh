#!/bin/bash
cd /home/claude/b3d
for i in 0 1 2 3 4 5 6 7 8 9; do
  echo "scene $i start $(date +%T)" >> bh/progress.log
  python3 bh3d.py $i anim > bh/log_$i.txt 2>&1
  echo "scene $i done $(date +%T) frames $(ls bh/s$i/*.png | wc -l)" >> bh/progress.log
done
echo ALLDONE >> bh/progress.log
