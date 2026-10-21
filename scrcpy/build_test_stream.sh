#!/bin/sh
set -eu

out=${1:-test.h264}
exec ffmpeg -hide_banner -loglevel error -y \
    -f lavfi -i testsrc=size=320x240:rate=30 \
    -t 1 -c:v libx264 -preset ultrafast -tune zerolatency -x264-params aud=1 \
    -pix_fmt yuv420p -f h264 "$out"
