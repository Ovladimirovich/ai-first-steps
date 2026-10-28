#!/usr/bin/env bash
# Порционный рендер для машин с малой RAM: куски по 1500 кадров, concurrency 1, склейка без перекодирования.
# usage: tools/render_chunks.sh final.mp4 [--props='{"subs":false}']
set -e
OUT=$1; shift; PROPS="$@"
cd "$(dirname "$0")/../remotion"
TOTAL=$(python3 -c "import json;t=json.load(open('public/timing.json'));print(int((t['total']+9)*30))")
STEP=1500; mkdir -p ../release/chunks; : > ../release/chunks/list_$OUT.txt
for ((s=0; s<TOTAL; s+=STEP)); do
  e=$(( s+STEP-1 )); [ $e -ge $TOTAL ] && e=$(( TOTAL-1 ))
  f=../release/chunks/${OUT%.mp4}_$(printf %05d $s).mp4
  [ -s "$f" ] || npx remotion render src/index.ts Main "$f" --frames=$s-$e --codec h264 --crf 18 --concurrency 1 --log=error $PROPS
  echo "file '$(basename $f)'" >> ../release/chunks/list_$OUT.txt
  echo "chunk $s-$e done"
done
FF=$(python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
cd ../release/chunks && $FF -y -v error -f concat -safe 0 -i list_$OUT.txt -c copy ../$OUT && echo "DONE $OUT"
