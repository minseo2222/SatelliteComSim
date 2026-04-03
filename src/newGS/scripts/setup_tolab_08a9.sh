#!/usr/bin/env bash
# cFS TO_LAB 초기화: NOOP → OUTPUT_ENABLE → ADD_PKT(0x08A9)
# 사용: scripts/setup_tolab_08a9.sh
# 환경:
#   HOST(기본 127.0.0.1)       : GroundSystem uplink 수신 주소
#   PORT(기본 50000)           : GroundSystem uplink 수신 포트
#   CLIENT(기본 127.0.0.1)     : TO_LAB가 텔레메트리를 보낼 목적지 IP
#   CMD(기본 ./Subsystems/cmdUtil/cmdUtil)

set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-50000}"
CLIENT="${CLIENT:-127.0.0.1}"
CMD="${CMD:-./Subsystems/cmdUtil/cmdUtil}"

if [ ! -x "$CMD" ]; then
  echo "ERROR: cmdUtil not found/executable at $CMD" >&2
  exit 1
fi

# 0) NOOP
"$CMD" --host="$HOST" --port="$PORT" --pktid=0x1880 --cmdcode=0 >/dev/null

# 1) OUTPUT ENABLE
# TO_LAB 현재 구현은 목적지 IP 문자열 payload를 요구한다.
"$CMD" --host="$HOST" --port="$PORT" --pktid=0x1880 --cmdcode=6 \
  --string="17:${CLIENT}" >/dev/null

# 2) ADD_PKT: SAMPLE_APP_TEXT_TLM = 0x08A9
# 바이트열(엔디안 보정): A9 08  00 00  00  00  04 00
"$CMD" --host="$HOST" --port="$PORT" --pktid=0x1880 --cmdcode=2 \
  --uint8=0xA9 --uint8=0x08 --uint8=0x00 --uint8=0x00 \
  --uint8=0x00 --uint8=0x00 --uint8=0x04 --uint8=0x00 >/dev/null

echo "[OK] TO_LAB enabled for ${CLIENT} + 0x08A9 registered (limit=4) on $HOST:$PORT"
