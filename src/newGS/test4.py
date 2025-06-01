#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test4.py: test3로부터 GMSK 변조 데이터를 수신하여 복조.
          GMSK 프리앰블 제거 후 남은 cFS 원본 CCSDS 패킷에서
          순수 "ID:메시지" 문자열을 추출하여 core_message_bits로 CSV에 기록.
          CSV 로그의 ID는 cFS 패킷 내 "ID:메시지"의 ID를 우선 사용.
          match_status와 ber는 CSV에 기록하지 않음.
"""

import socket
import datetime # datetime.timezone 사용
import os
import csv
from pathlib import Path
import numpy as np
from gnuradio import gr, blocks, digital

# test3 -> test4 (GMSK 변조 데이터 수신)
LISTEN_IP_FROM_TEST3 = "0.0.0.0"
LISTEN_PORT_FROM_TEST3 = 8890

ROOTDIR = Path(__file__).resolve().parent
# sample_app_tlm_page.py가 기대하는 경로 (test1.py의 SENT_CSV와 동일 디렉토리)
RECV_CSV_PATH = ROOTDIR / "Subsystems" / "cmdGui" / "sample_app_recv.csv"

GMSK_RX_PREAMBLE = b'\xAA\xAA'
CFS_CCSDS_PRIMARY_HEADER_LENGTH = 6
CFS_SAMPLE_APP_APID = 0x0A9 # test3.py가 필터링하는 SAMPLE_APP_MID
CFS_SAMPLE_APP_INTERNAL_PAYLOAD_PREFIX_LEN = 10
CFS_SAMPLE_APP_TEXT_PREFIX = "수신한 텍스트: "

def demodulate_gmsk_signal(complex_samples_array: np.ndarray) -> bytes:
    sps = 2
    fg = gr.top_block(name="GMSK_Demod_Flowgraph_Test4")
    src = blocks.vector_source_c(list(complex_samples_array), repeat=False)
    gmsk_demod = digital.gmsk_demod(samples_per_symbol=sps, verbose=False, log=False)
    unpacked_to_packed = blocks.unpacked_to_packed_bb(1, gr.GR_MSB_FIRST)
    sink = blocks.vector_sink_b()
    fg.connect(src, gmsk_demod, unpacked_to_packed, sink)
    fg.run()
    return bytes(sink.data())

def bytes_to_bitstring(b: bytes) -> str:
    return ''.join(f'{byte:08b}' for byte in b)

def ensure_recv_csv_header():
    if not RECV_CSV_PATH.exists() or RECV_CSV_PATH.stat().st_size == 0:
        RECV_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RECV_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # 수정된 CSV 헤더: match_status, ber 컬럼 제거
            writer.writerow(["id", "timestamp", "text_representation", "core_message_bits"])
        print(f"[DEBUG] Created CSV header for received data at {RECV_CSV_PATH}")

# log_to_recv_csv 함수 시그니처 변경: match_status, ber 인자 제거
def log_to_recv_csv(log_id, timestamp_str, text_representation, core_message_bits):
    ensure_recv_csv_header()
    with open(RECV_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # 수정된 컬럼에 맞춰 데이터 기록
        writer.writerow([str(log_id), timestamp_str, text_representation, core_message_bits])
    print(f"[DEBUG] Logged to RECV CSV: ID='{str(log_id)}', Text='{text_representation}', Core Message Bits={len(core_message_bits)}")

def main():
    sock_recv_from_test3 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_recv_from_test3.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_recv_from_test3.bind((LISTEN_IP_FROM_TEST3, LISTEN_PORT_FROM_TEST3))
    print(f"[test4.py] Listening for GMSK data from test3 on UDP {LISTEN_IP_FROM_TEST3}:{LISTEN_PORT_FROM_TEST3} ...")

    t4_processing_seq_count = 0 # 대체 ID 생성용 카운터

    while True:
        gmsk_modulated_data_from_test3, test3_addr = sock_recv_from_test3.recvfrom(65536)
        print(f"\n[test4.py] Received {len(gmsk_modulated_data_from_test3)} GMSK bytes from test3 ({test3_addr})")

        try:
            complex_samples = np.frombuffer(gmsk_modulated_data_from_test3, dtype=np.complex64)
            if complex_samples.size == 0: continue
        except Exception as e:
            print(f"[ERROR] Convert to complex samples failed: {e}"); continue

        try:
            demodulated_stream = demodulate_gmsk_signal(complex_samples)
            if not demodulated_stream: continue
        except Exception as e:
            print(f"[ERROR] GMSK Demodulation failed: {e}"); import traceback; traceback.print_exc(); continue
        
        preamble_idx = demodulated_stream.find(GMSK_RX_PREAMBLE)
        if preamble_idx == -1:
            print(f"[WARN] GMSK RX Preamble ({GMSK_RX_PREAMBLE.hex()}) not found."); continue
        
        start_of_cfs_packet = preamble_idx + len(GMSK_RX_PREAMBLE)
        cfs_original_packet_data = demodulated_stream[start_of_cfs_packet:]

        if not cfs_original_packet_data:
            print("[WARN] No data after GMSK preamble."); continue
        
        # --- 핵심 "ID:메시지" 문자열 추출 및 로깅 준비 ---
        core_message_bytes_for_log = b""
        parsed_numeric_id_from_payload = None
        text_repr_for_csv = "[CoreMsgParseError]"
        # 기본 로그 ID는 cFS 패킷 헤더에서 추출 (또는 더 단순한 카운터)
        log_id_from_cfs_header = f"T4_ProcSeq_{t4_processing_seq_count}"

        try:
            if len(cfs_original_packet_data) >= CFS_CCSDS_PRIMARY_HEADER_LENGTH:
                cfs_pkt_apid_field = ((cfs_original_packet_data[0] & 0x07) << 8) | cfs_original_packet_data[1]
                cfs_pkt_seq_count_field = ((cfs_original_packet_data[2] & 0x3F) << 8) | cfs_original_packet_data[3]
                log_id_from_cfs_header = f"cFS_APID{cfs_pkt_apid_field:03X}_SEQ{cfs_pkt_seq_count_field}"

                cfs_pkt_data_len_field = (cfs_original_packet_data[4] << 8) | cfs_original_packet_data[5]
                expected_cfs_user_data_len = 0 if cfs_pkt_data_len_field == 0xFFFF else cfs_pkt_data_len_field + 1
                actual_available_user_data_len = len(cfs_original_packet_data) - CFS_CCSDS_PRIMARY_HEADER_LENGTH
                
                user_data_to_parse_len = 0
                if actual_available_user_data_len < 0:
                    text_repr_for_csv = "[InsufficientDataForPayload]"
                    core_message_bytes_for_log = b""
                else:
                    if actual_available_user_data_len < expected_cfs_user_data_len:
                        user_data_to_parse_len = actual_available_user_data_len
                    elif actual_available_user_data_len > expected_cfs_user_data_len:
                        user_data_to_parse_len = expected_cfs_user_data_len
                    else: user_data_to_parse_len = expected_cfs_user_data_len
                    
                    if user_data_to_parse_len > 0:
                        user_data_start_idx = CFS_CCSDS_PRIMARY_HEADER_LENGTH
                        user_data_end_idx = user_data_start_idx + user_data_to_parse_len
                        if user_data_end_idx > len(cfs_original_packet_data):
                            user_data_end_idx = len(cfs_original_packet_data)
                        
                        user_data_bytes = cfs_original_packet_data[user_data_start_idx : user_data_end_idx]

                        if cfs_pkt_apid_field == CFS_SAMPLE_APP_APID and len(user_data_bytes) > CFS_SAMPLE_APP_INTERNAL_PAYLOAD_PREFIX_LEN:
                            actual_string_data_start_idx = CFS_SAMPLE_APP_INTERNAL_PAYLOAD_PREFIX_LEN
                            actual_string_data_bytes = user_data_bytes[actual_string_data_start_idx:]
                            
                            decoded_app_payload_str = actual_string_data_bytes.decode('utf-8', errors='replace').rstrip('\x00')
                            
                            if decoded_app_payload_str.startswith(CFS_SAMPLE_APP_TEXT_PREFIX):
                                content_after_text_prefix = decoded_app_payload_str[len(CFS_SAMPLE_APP_TEXT_PREFIX):]
                                
                                core_message_bytes_for_log = content_after_text_prefix.encode('utf-8') # 핵심 메시지 바이트
                                parts = content_after_text_prefix.split(":", 1)
                                if len(parts) == 2:
                                    id_str_from_payload = parts[0].strip()
                                    text_repr_for_csv = parts[1].strip()
                                    try:
                                        parsed_numeric_id_from_payload = int(id_str_from_payload)
                                    except ValueError:
                                        text_repr_for_csv = content_after_text_prefix 
                                else: text_repr_for_csv = content_after_text_prefix
                            else: 
                                text_repr_for_csv = decoded_app_payload_str
                                core_message_bytes_for_log = decoded_app_payload_str.encode('utf-8')
                        else: 
                            decoded_user_data = user_data_bytes.decode('utf-8', errors='replace').rstrip('\x00')
                            if decoded_user_data:
                                text_repr_for_csv = decoded_user_data
                                core_message_bytes_for_log = user_data_bytes # 일반 UserData는 전체를 핵심으로 간주
                            else:
                                text_repr_for_csv = "[EmptyDecodedUserData]" if user_data_bytes else "[NoUserDataBytes]"
                                core_message_bytes_for_log = b""
                    elif user_data_to_parse_len == 0:
                        text_repr_for_csv = "[NoUserDataInCFSPacket]"
                        core_message_bytes_for_log = b""
            else: 
                text_repr_for_csv = cfs_original_packet_data.hex() if cfs_original_packet_data else "[EmptyCFSPacket]"
                core_message_bytes_for_log = cfs_original_packet_data # 헤더 파싱 불가 시 전체를 로깅
        except Exception as e:
            print(f"[WARN] Error parsing cFS packet content for logging: {e}")
            text_repr_for_csv = cfs_original_packet_data.hex() if cfs_original_packet_data else "[CFSPacketParseError]"
            core_message_bytes_for_log = cfs_original_packet_data # 예외 발생 시 전체를 로깅

        core_message_bits_for_log = bytes_to_bitstring(core_message_bytes_for_log)
        final_log_id_for_csv = parsed_numeric_id_from_payload if parsed_numeric_id_from_payload is not None else log_id_from_cfs_header
        
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')
        if not timestamp_str.endswith('Z'): # isoformat이 +00:00을 생성할 수 있으므로 Z로 통일 (Python < 3.11)
             timestamp_str = timestamp_str.replace('+00:00', 'Z')
        
        # match_status와 ber 인자 없이 호출
        log_to_recv_csv(final_log_id_for_csv, timestamp_str, text_repr_for_csv, core_message_bits_for_log)
        
        if parsed_numeric_id_from_payload is None:
            t4_processing_seq_count += 1

if __name__ == "__main__":
    main()
