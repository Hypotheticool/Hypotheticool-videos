#!/bin/bash
cd /home/claude/b3d
for i in 0 1 2 3 4 5 6 7 8; do
  echo "scene $i start $(date +%T)" >> sunbh/progress.log
  python3 sunbh3d.py $i anim > sunbh/log_$i.txt 2>&1
  echo "scene $i done $(date +%T) frames $(ls sunbh/s$i/*.png | wc -l)" >> sunbh/progress.log
done
echo ALLDONE >> sunbh/progress.log
