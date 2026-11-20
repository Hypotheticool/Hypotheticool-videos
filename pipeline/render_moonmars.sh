#!/bin/bash
cd /home/claude/b3d
for i in 0 1 2 3 4 5 6 7 8 9 10; do
  echo "scene $i start $(date +%T)" >> moonmars/progress.log
  python3 moonmars3d.py $i anim > moonmars/log_$i.txt 2>&1
  echo "scene $i done $(date +%T) frames $(ls moonmars/s$i/f_*.png | wc -l)" >> moonmars/progress.log
done
echo ALLDONE >> moonmars/progress.log
