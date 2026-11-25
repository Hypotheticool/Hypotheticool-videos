#!/bin/bash
# renders 3D scenes in order until DEADLINE (epoch s); encodes each finished scene into the repo's work folder
export HC_W=1920 HC_H=1080
cd /home/claude/b3d
SLUG=moon-full-story; ROOT=/home/claude/b3d/$SLUG; WORK=/home/claude/hypotheticool-videos/work/$SLUG
mkdir -p $WORK
for i in "$@"; do
  if [ $(date +%s) -gt $DEADLINE ]; then echo "deadline before $i" >> queue.log; break; fi
  echo "start $i $(date +%T)" >> queue.log
  rm -rf $ROOT/s$i
  python3 scenes3d_$SLUG.py $i anim > r$i.log 2>&1
  n=$(ls $ROOT/s$i/f_*.png 2>/dev/null | wc -l); want=$(python3 -c "import json;print(json.load(open('$ROOT/s$i/meta.json'))['frames'])")
  if [ "$n" = "$want" ]; then
    ffmpeg -y -loglevel error -framerate 24 -i $ROOT/s$i/f_%04d.png -c:v libx264 -crf 12 -pix_fmt yuv420p $WORK/s$i.mp4 && cp $ROOT/s$i/meta.json $WORK/s$i.json
    echo "done $i $n frames $(date +%T)" >> queue.log
  else echo "FAIL $i ($n/$want) $(date +%T)" >> queue.log; fi
done
echo QUEUE_END >> queue.log
