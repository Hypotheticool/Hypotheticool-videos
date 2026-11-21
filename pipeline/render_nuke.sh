#!/bin/bash
cd /home/claude/b3d
for i in 0 1 2 3 4 5 6 7 8 9 10 11 12; do
  echo "scene $i start $(date +%T)" >> nuke/progress.log
  python3 nuke3d.py $i anim < /dev/null > nuke/log_$i.txt 2>&1
  echo "scene $i done $(date +%T) frames $(ls nuke/s$i/f_*.png | wc -l)" >> nuke/progress.log
done
echo ALLDONE >> nuke/progress.log
