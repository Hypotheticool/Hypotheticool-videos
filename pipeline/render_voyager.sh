#!/bin/bash
cd /home/claude/b3d
for i in 0 1 2 3 4 5 6 7 8 9; do
  echo "scene $i start $(date +%T)" >> voyager/progress.log
  python3 voyager3d.py $i anim > voyager/log_$i.txt 2>&1
  echo "scene $i done $(date +%T) frames $(ls voyager/s$i/f_*.png | wc -l)" >> voyager/progress.log
done
echo ALLDONE >> voyager/progress.log
