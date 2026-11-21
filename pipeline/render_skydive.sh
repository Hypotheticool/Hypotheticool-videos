#!/bin/bash
cd /home/claude/b3d
for i in 0 1 2 3 4 5 6 7 8 9 10 11; do
  echo "scene $i start $(date +%T)" >> skydive/progress.log
  python3 skydive3d.py $i anim > skydive/log_$i.txt 2>&1
  echo "scene $i done $(date +%T) frames $(ls skydive/s$i/f_*.png | wc -l)" >> skydive/progress.log
done
echo ALLDONE >> skydive/progress.log
