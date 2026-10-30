#!/usr/bin/env bash
# Надёжный чанковый рендер Pixar-версии — устойчив к обрывам, можно перезапускать.
# Куски по 1500 кадров, concurrency 1, склейка без перекодирования.
# Требует: LD_LIBRARY_PATH=/tmp/al2023/lib:/tmp FONTCONFIG_PATH=/tmp/fonts
# usage: tools/render_pixar_chunks.sh pixar-why-ai-full.mp4
set -e
OUT=${1:-pixar-why-ai-full.mp4}
CHROME=${CHROME:-/tmp/chromium}
cd "$(dirname "$0")/../remotion"
TOTAL=$(python3 -c "import json; j=json.load(open('public/timing-pixar.json')); print(int((j['total']+6)*30))")
STEP=1500
CHUNK_DIR="../preview/chunks_pixar"
mkdir -p "$CHUNK_DIR"
LIST="$CHUNK_DIR/list_${OUT}.txt"
: > "$LIST"
echo "Pixar chunks: total $TOTAL frames, step $STEP, chrome $CHROME"
for ((s=0; s<TOTAL; s+=STEP)); do
  e=$(( s+STEP-1 )); [ $e -ge $TOTAL ] && e=$(( TOTAL-1 ))
  f="$CHUNK_DIR/${OUT%.mp4}_$(printf %05d $s).mp4"
  if [ -s "$f" ]; then
    echo "SKIP chunk $s-$e exists $(du -h "$f" | cut -f1)"
  else
    echo "RENDER chunk $s-$e -> $f"
    # прокидываем либы для хрома
    LD_LIBRARY_PATH=/tmp/al2023/lib:/tmp:$LD_LIBRARY_PATH FONTCONFIG_PATH=/tmp/fonts HOME=/tmp \
    npx remotion render src/index.ts PixarWhyAI "$f" --frames=$s-$e --codec h264 --crf 18 --concurrency 1 --browser-executable="$CHROME" --log=verbose
    echo "DONE chunk $s-$e"
  fi
  echo "file '$(basename "$f")'" >> "$LIST"
done
echo "Склейка $LIST -> ../release/$OUT и ../preview/$OUT"
FF=$(python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")
mkdir -p ../release ../preview
cd "$CHUNK_DIR" && $FF -y -v error -f concat -safe 0 -i "list_${OUT}.txt" -c copy "../../release/$OUT" 2>&1 | head -20
cp "../../release/$OUT" "../../preview/$OUT" 2>&1 | head -5
ls -lh "../../release/$OUT" "../../preview/$OUT" 2>&1 | head -10
echo "DONE $OUT"
