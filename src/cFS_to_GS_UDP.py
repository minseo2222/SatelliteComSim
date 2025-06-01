import socket
import struct

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 1235))  # TO_LAB_TLM_PORT와 일치해야 함

def get_msg_id(data):
    # CFE 기본: 2바이트 MID, big-endian (MSB first)
    return struct.unpack_from(">H", data)[0]

print("Listening on UDP port 1235...")
while True:
    data, addr = sock.recvfrom(2048)
    msg_id = get_msg_id(data)

    if msg_id == 0x08A9:
        # sample_app 텍스트 텔레메트리일 경우만 출력
        try:
            text = data.decode("utf-8", errors="ignore")
            print(f"[sample_app 텍스트] {text}")
        except:
            print("[sample_app 텍스트] (디코딩 실패)")
    else:
        # 그 외 MID는 무시하거나 필요시 따로 기록
        pass

