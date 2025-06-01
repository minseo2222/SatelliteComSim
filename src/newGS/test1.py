#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test1.py: GS(cmdUtil)로부터 수신한 패킷에서 순수 "ID:메시지" 문자열을 추출하여 로깅.
          수신한 전체 패킷(gs_packet_data)에 GMSK 전송 프리앰블만 추가하여
          GMSK 변조 후 test2.py로 전송.
"""

import socket
import time
import csv
import os
from pathlib import Path
from datetime import datetime, timezone # timezone 추가
import numpy as np
from gnuradio import gr, blocks, digital

# GS -> test1 (cmdUtil 통해 패킷 입력)
LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 50000

# test1 -> test2 (GMSK 변조 데이터 전송)
UDP_IP_SEND_TO_TEST2 = "127.0.0.1"
UDP_PORT_SEND_TO_TEST2 = 8888

ROOTDIR = Path(__file__).resolve().parent
SENT_CSV_PATH = ROOTDIR / "Subsystems" / "cmdGui" / "sample_app_sent.csv"
ATTACK_FILE = ROOTDIR / "attack_mode.txt" # GroundSystem.py가 이 파일을 제어

GMSK_TX_PREAMBLE = b'\xAA\xAA'

class GMSKModulator(gr.top_block):
    def __init__(self, data_bytes_to_modulate):
        super().__init__(name="GMSKModulator_Test1")
        self.sps = 2
        self.bt = 0.3 # test2.py의 demodulator 기본 bt값과 일치
        self.src = blocks.vector_source_b(list(data_bytes_to_modulate), False)
        self.mod = digital.gmsk_mod(samples_per_symbol=self.sps, bt=self.bt)
        self.sink = blocks.vector_sink_c()
        self.connect(self.src, self.mod)
        self.connect(self.mod, self.sink)

    def get_modulated_data(self):
        return self.sink.data()

def get_attack_mode():
    try:
        # GroundSystem.py가 이 파일을 생성/수정하므로, 여기서 읽기만 함
        if ATTACK_FILE.exists():
            with open(ATTACK_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        else: # 파일이 없으면 "none"으로 간주 (GroundSystem.py 초기화 시 생성됨)
            return "none"
    except Exception as e:
        print(f"[WARN] Could not read attack_mode.txt: {e}")
        return "none"

def bytes_to_bitstring(b: bytes) -> str:
    return ''.join(f"{byte:08b}" for byte in b)

def ensure_sent_csv_header():
    if not SENT_CSV_PATH.exists() or SENT_CSV_PATH.stat().st_size == 0:
        SENT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SENT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # CSV 헤더: BER 비교 대상인 핵심 메시지 비트열을 명시
            writer.writerow(["id", "timestamp", "text_representation", "core_message_bits", "attack_type"])
        print(f"[DEBUG] Created CSV header for sent data at {SENT_CSV_PATH}")

def log_to_sent_csv(log_id, timestamp_str, text_representation, core_message_bits, attack_mode):
    ensure_sent_csv_header()
    with open(SENT_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([str(log_id), timestamp_str, text_representation, core_message_bits, attack_mode])
    print(f"[DEBUG] Logged to SENT CSV: ID='{str(log_id)}', Text='{text_representation}', Core Message Bits={len(core_message_bits)}")

def main():
    sock_recv_from_gs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_recv_from_gs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_recv_from_gs.bind((LISTEN_IP, LISTEN_PORT))
    print(f"[test1.py] Listening for packets from GS (via cmdUtil) on UDP {LISTEN_IP}:{LISTEN_PORT} ...")

    sock_send_to_test2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # test1.py의 자체 처리 시퀀스 카운터 (로그 대체 ID용)
    t1_processing_seq_count = 0

    while True:
        gs_packet_data, gs_addr = sock_recv_from_gs.recvfrom(4096)
        print(f"\n[test1.py] Received {len(gs_packet_data)} bytes of packet data from GS ({gs_addr})")
        
        # --- 핵심 "ID:메시지" 문자열 추출 및 로깅 준비 ---
        core_message_bytes_for_log = b""
        parsed_numeric_id_from_gui = None
        text_repr_for_csv = "[CoreMsgParseError]"
        # 대체 ID 초기화: test1.py 자체 처리 시퀀스 사용
        fallback_log_id_str = f"T1_ProcSeq_{t1_processing_seq_count}" 

        CMDUTIL_CCSDS_PRI_HDR_LEN = 6
        CMDUTIL_INTERNAL_HDR_LEN = 2 # cmdUtil이 추가하는 내부 헤더 (예: cmdcode 0x0A + unknown 0x18)
        CMDUTIL_STRING_FIELD_LEN = 128 # cmdUtil이 "ID:메시지" 문자열을 위해 할당한 필드 길이

        try: # 대체 ID를 cmdUtil 패킷 헤더 정보로 업데이트 시도
            if len(gs_packet_data) >= CMDUTIL_CCSDS_PRI_HDR_LEN:
                cmdutil_apid_field = ((gs_packet_data[0] & 0x07) << 8) | gs_packet_data[1]
                cmdutil_seq_count_field = ((gs_packet_data[2] & 0x3F) << 8) | gs_packet_data[3]
                fallback_log_id_str = f"CmdPkt_APID{cmdutil_apid_field:03X}_SEQ{cmdutil_seq_count_field}"
        except IndexError:
            print(f"[WARN] Could not parse cmdUtil CCSDS header from gs_packet_data for fallback ID. Length: {len(gs_packet_data)}")
            # fallback_log_id_str는 초기값(T1_ProcSeq_...) 유지

        # cmdUtil 패킷에서 실제 "ID:메시지" 문자열 부분 추출
        expected_min_len_for_string = CMDUTIL_CCSDS_PRI_HDR_LEN + CMDUTIL_INTERNAL_HDR_LEN
        if len(gs_packet_data) > expected_min_len_for_string: # 최소한 문자열 시작부분까지 데이터가 있어야 함
            string_payload_field_start = expected_min_len_for_string
            # cmdUtil이 할당한 128바이트 문자열 필드를 추출하되, 실제 패킷 길이를 넘지 않도록 함
            actual_string_field_len = min(CMDUTIL_STRING_FIELD_LEN, len(gs_packet_data) - string_payload_field_start)
            string_payload_field_bytes = gs_packet_data[string_payload_field_start : string_payload_field_start + actual_string_field_len]
            
            try:
                # UTF-8 디코딩 후, 후미의 널 패딩 제거하여 원본 "ID:메시지" 문자열 복원
                # sample_app_send_text_gui.py에서 이미 [:128]로 잘랐으므로, 
                # 여기서 추출한 string_payload_field_bytes는 이미 원본이거나, 원본 + 널패딩임.
                decoded_core_message_str = string_payload_field_bytes.decode('utf-8', errors='replace').rstrip('\x00')
                
                # 로깅 대상: 복원된 (널패딩 제거된) 문자열의 UTF-8 바이트
                core_message_bytes_for_log = decoded_core_message_str.encode('utf-8')
                print(f"[DEBUG] Extracted core message for logging: '{decoded_core_message_str}' ({len(core_message_bytes_for_log)} bytes)")

                parts = decoded_core_message_str.split(":", 1)
                if len(parts) == 2: # "ID:TEXT" 형식인지 확인
                    id_str_from_gui = parts[0].strip()
                    text_repr_for_csv = parts[1].strip() # 메시지 부분
                    try:
                        parsed_numeric_id_from_gui = int(id_str_from_gui) # 정수 ID 변환
                    except ValueError:
                        print(f"[WARN] Parsed ID '{id_str_from_gui}' from GS packet is not an integer. Using fallback ID logic.")
                        # ID가 정수가 아니면, 파싱된 ID 문자열과 TEXT를 합쳐서 text_repr_for_csv로 사용
                        text_repr_for_csv = decoded_core_message_str 
                elif decoded_core_message_str: # 콜론이 없지만 내용이 있는 경우
                    text_repr_for_csv = decoded_core_message_str.strip()
                else: # 디코딩 후 빈 문자열 (모두 널패딩이었던 경우 등)
                    text_repr_for_csv = "[EmptyCoreMessage]"
                    core_message_bytes_for_log = b"" 
            except Exception as e:
                print(f"[WARN] Could not parse core message string from gs_packet_data: {e}")
                text_repr_for_csv = "[CoreMsgParseFail]"
                core_message_bytes_for_log = b"" # 파싱 실패 시 비트열도 비움
        else: 
            print(f"[WARN] gs_packet_data (len: {len(gs_packet_data)}) too short to extract core message string.")
            text_repr_for_csv = gs_packet_data.hex() if gs_packet_data else "[EmptyGSPacket]"
            core_message_bytes_for_log = b""


        core_message_bits_for_log = bytes_to_bitstring(core_message_bytes_for_log)
        # 최종 로그 ID 결정: GUI에서 온 정수 ID를 최우선 사용
        final_log_id_for_csv = parsed_numeric_id_from_gui if parsed_numeric_id_from_gui is not None else fallback_log_id_str
        
        # 타임스탬프: UTC 기준 ISO 8601 형식
        timestamp_str = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        if not timestamp_str.endswith('Z'): # isoformat이 +00:00을 생성할 수 있으므로 Z로 통일
            timestamp_str = timestamp_str.replace('+00:00', 'Z')

        attack_mode = get_attack_mode()

        log_to_sent_csv(final_log_id_for_csv, timestamp_str, text_repr_for_csv, core_message_bits_for_log, attack_mode)

        # test2.py로 전송할 패킷: gs_packet_data 전체에 GMSK 프리앰블만 추가
        packet_to_modulate = GMSK_TX_PREAMBLE + gs_packet_data
        
        print(f"[DEBUG] Packet to modulate for test2: {len(GMSK_TX_PREAMBLE)}B GMSK_preamble + {len(gs_packet_data)}B (gs_packet_data) = {len(packet_to_modulate)}B total")

        tb_mod = GMSKModulator(packet_to_modulate)
        tb_mod.run() # VectorSource가 repeat=False이므로, 데이터 소진 시 자동 완료
        
        modulated_complex_data = tb_mod.get_modulated_data()
        mod_bytes_to_test2 = np.array(modulated_complex_data, dtype=np.complex64).tobytes()
        
        sock_send_to_test2.sendto(mod_bytes_to_test2, (UDP_IP_SEND_TO_TEST2, UDP_PORT_SEND_TO_TEST2))
        print(f"[test1.py] Sent {len(mod_bytes_to_test2)} GMSK-modulated bytes to test2 ({UDP_IP_SEND_TO_TEST2}:{UDP_PORT_SEND_TO_TEST2})")
        
        t1_processing_seq_count += 1

if __name__ == "__main__":
    main()
