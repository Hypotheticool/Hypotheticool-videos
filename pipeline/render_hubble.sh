#!/bin/bash
cd /home/claude/b3d
for i in 0 1 2 3 4 5 6 7 8; do
  echo "scene $i start $(date +%T)" >> hubble/progress.log
  python3 hubble3d.py $i anim > hubble/log_$i.txt 2>&1
  echo "scene $i done $(date +%T) frames $(ls hubble/s$i/*.png | wc -l)" >> hubble/progress.log
done
echo ALLDONE >> hubble/progress.log
