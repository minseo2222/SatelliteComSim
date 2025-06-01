#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test1.py: GS(cmdUtil)로부터 수신한 패킷에서 순수 "ID:메시지" 문자열을 추출하여 로깅.
          GroundSystem.py에서 설정한 attack_mode.txt를 읽어 공격 적용.
          "변조", "노이즈", "재밍" 공격은 "ID:메시지"의 메시지 텍스트 부분에만 적용 (ID 보호).
          수신한 전체 패킷(gs_packet_data)에 GMSK 전송 프리앰블만 추가하여
          GMSK 변조 후 test2.py로 전송.
"""

import socket
import time
import csv
import os
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from gnuradio import gr, blocks, digital
import random # 비트 오류 주입용

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 50000
UDP_IP_SEND_TO_TEST2 = "127.0.0.1"
UDP_PORT_SEND_TO_TEST2 = 8888

ROOTDIR = Path(__file__).resolve().parent
SENT_CSV_PATH = ROOTDIR / "Subsystems" / "cmdGui" / "sample_app_sent.csv"
ATTACK_FILE = ROOTDIR / "attack_mode.txt"
GMSK_TX_PREAMBLE = b'\xAA\xAA'

# --- GMSKModulator, get_attack_mode, bytes_to_bitstring, CSV 함수들은 이전과 동일 ---
class GMSKModulator(gr.top_block):
    def __init__(self, data_bytes_to_modulate):
        super().__init__(name="GMSKModulator_Test1")
        self.sps = 2; self.bt = 0.3
        self.src = blocks.vector_source_b(list(data_bytes_to_modulate), False)
        self.mod = digital.gmsk_mod(samples_per_symbol=self.sps, bt=self.bt)
        self.sink = blocks.vector_sink_c()
        self.connect(self.src, self.mod); self.connect(self.mod, self.sink)
    def get_modulated_data(self): return self.sink.data()

def get_attack_mode():
    try:
        if ATTACK_FILE.exists():
            with open(ATTACK_FILE, "r", encoding="utf-8") as f:
                return f.read().strip().lower()
        else: return "none"
    except Exception as e:
        print(f"[WARN] Could not read attack_mode.txt: {e}"); return "none"

def bytes_to_bitstring(b: bytes) -> str:
    return ''.join(f"{byte:08b}" for byte in b)

def ensure_sent_csv_header():
    if not SENT_CSV_PATH.exists() or SENT_CSV_PATH.stat().st_size == 0:
        SENT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SENT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "timestamp", "text_representation", "core_message_bits", "attack_type"])
        print(f"[DEBUG] Created CSV header for sent data at {SENT_CSV_PATH}")

def log_to_sent_csv(log_id, timestamp_str, text_representation, core_message_bits, attack_mode):
    ensure_sent_csv_header()
    with open(SENT_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([str(log_id), timestamp_str, text_representation, core_message_bits, attack_mode])
    print(f"[DEBUG] Logged to SENT CSV: ID='{str(log_id)}', Text='{text_representation}', Core Message Bits={len(core_message_bits)}, Attack='{attack_mode}'")
# --- Helper functions end ---

def apply_payload_bit_errors(payload_bytes: bytes, error_rate: float) -> bytes:
    """ 주어진 페이로드 바이트에 지정된 비율만큼 비트 오류를 주입 (ID 보호 없음, 전체 페이로드 대상) """
    if not payload_bytes or error_rate == 0:
        return payload_bytes
    
    bits = []
    for byte in payload_bytes:
        for i in range(8):
            bits.append((byte >> (7 - i)) & 1)
            
    num_bits_to_flip = int(len(bits) * error_rate)
    if num_bits_to_flip == 0 and error_rate > 0: # 최소 1비트는 변경 (error_rate가 매우 작을 때)
        num_bits_to_flip = 1 
        
    indices_to_flip = random.sample(range(len(bits)), min(num_bits_to_flip, len(bits)))
    
    for idx in indices_to_flip:
        bits[idx] = 1 - bits[idx] # 비트 반전
        
    new_bytes = bytearray()
    for i in range(0, len(bits), 8):
        byte_val = 0
        for j in range(8):
            if (i + j) < len(bits):
                byte_val = (byte_val << 1) | bits[i+j]
        new_bytes.append(byte_val)
    return bytes(new_bytes)


def main():
    sock_recv_from_gs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_recv_from_gs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_recv_from_gs.bind((LISTEN_IP, LISTEN_PORT))
    print(f"[test1.py] Listening for packets from GS (via cmdUtil) on UDP {LISTEN_IP}:{LISTEN_PORT} ...")
    print(f"[test1.py] Attack mode file: {ATTACK_FILE.resolve()}")

    sock_send_to_test2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    t1_processing_seq_count = 0

    while True:
        gs_packet_data_original, gs_addr = sock_recv_from_gs.recvfrom(4096)
        print(f"\n[test1.py] Received {len(gs_packet_data_original)} bytes of packet data from GS ({gs_addr})")
        
        current_attack_mode = get_attack_mode()
        print(f"[test1.py] Current Attack Mode: {current_attack_mode}")

        # --- "ID:메시지" 핵심 평문 추출 (로깅용, 공격 전 원본 기준) ---
        core_message_bytes_for_log = b""
        parsed_numeric_id_from_gui = None
        text_repr_for_csv = "[CoreMsgParseError]"
        id_part_str_for_attack_handling = "" # 공격 시 ID 부분 식별 및 보호용
        fallback_log_id_str = f"T1_ProcSeq_{t1_processing_seq_count}" 

        CMDUTIL_CCSDS_PRI_HDR_LEN = 6
        CMDUTIL_INTERNAL_HDR_LEN = 2
        CMDUTIL_STRING_FIELD_LEN = 128 

        try: 
            if len(gs_packet_data_original) >= CMDUTIL_CCSDS_PRI_HDR_LEN:
                cmdutil_apid_field = ((gs_packet_data_original[0] & 0x07) << 8) | gs_packet_data_original[1]
                cmdutil_seq_count_field = ((gs_packet_data_original[2] & 0x3F) << 8) | gs_packet_data_original[3]
                fallback_log_id_str = f"CmdPkt_APID{cmdutil_apid_field:03X}_SEQ{cmdutil_seq_count_field}"
        except IndexError: pass

        expected_min_len_for_string_field = CMDUTIL_CCSDS_PRI_HDR_LEN + CMDUTIL_INTERNAL_HDR_LEN
        if len(gs_packet_data_original) > expected_min_len_for_string_field:
            string_payload_field_start = expected_min_len_for_string_field
            actual_string_field_len = min(CMDUTIL_STRING_FIELD_LEN, len(gs_packet_data_original) - string_payload_field_start)
            string_payload_field_bytes = gs_packet_data_original[string_payload_field_start : string_payload_field_start + actual_string_field_len]
            
            try:
                decoded_core_message_str = string_payload_field_bytes.decode('utf-8', errors='replace').rstrip('\x00')
                core_message_bytes_for_log = decoded_core_message_str.encode('utf-8')
                
                parts = decoded_core_message_str.split(":", 1)
                if len(parts) == 2:
                    id_str_from_gui = parts[0].strip()
                    id_part_str_for_attack_handling = id_str_from_gui # 공격 시 ID 부분 식별용
                    text_repr_for_csv = parts[1].strip()
                    try: parsed_numeric_id_from_gui = int(id_str_from_gui)
                    except ValueError: text_repr_for_csv = decoded_core_message_str 
                elif decoded_core_message_str: text_repr_for_csv = decoded_core_message_str.strip()
                else: text_repr_for_csv = "[EmptyCoreMessage]"; core_message_bytes_for_log = b""
            except Exception as e:
                text_repr_for_csv = "[CoreMsgParseFail]"; core_message_bytes_for_log = b"" 
        else: 
            text_repr_for_csv = gs_packet_data_original.hex() if gs_packet_data_original else "[EmptyGSPacket]"
            core_message_bytes_for_log = b""

        core_message_bits_for_log = bytes_to_bitstring(core_message_bytes_for_log)
        final_log_id_for_csv = parsed_numeric_id_from_gui if parsed_numeric_id_from_gui is not None else fallback_log_id_str
        timestamp_str = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        
        log_to_sent_csv(final_log_id_for_csv, timestamp_str, text_repr_for_csv, core_message_bits_for_log, current_attack_mode)

        # --- 공격 적용 ---
        data_to_transmit_attacked = bytearray(gs_packet_data_original) 

        if current_attack_mode == "drop":
            print(f"[ATTACK][test1.py] Dropping packet for ID '{final_log_id_for_csv}'.")
            t1_processing_seq_count += 1
            continue 
        
        # "modify", "noise", "jamming"은 "ID:메시지"의 메시지 텍스트 부분에만 적용
        if current_attack_mode in ["modify", "noise", "jamming"]:
            print(f"[ATTACK][test1.py] Applying '{current_attack_mode}' attack for ID '{final_log_id_for_csv}'.")
            
            if id_part_str_for_attack_handling and text_repr_for_csv not in ["[CoreMsgParseError]", "[CoreMsgParseFail]", "[EmptyCoreMessage]", "[PktParseError]", gs_packet_data_original.hex()]:
                
                id_prefix_str = f"{id_part_str_for_attack_handling}:"
                id_prefix_bytes = id_prefix_str.encode('utf-8')
                id_prefix_len_in_bytes = len(id_prefix_bytes)

                # "ID:메시지" 문자열 필드가 시작되는 위치 (gs_packet_data_original 기준)
                string_field_absolute_start = CMDUTIL_CCSDS_PRI_HDR_LEN + CMDUTIL_INTERNAL_HDR_LEN
                
                # 실제 "메시지" 텍스트가 시작되는 절대 오프셋
                message_text_absolute_start_offset = string_field_absolute_start + id_prefix_len_in_bytes
                
                # 원본 "메시지" 텍스트 부분의 바이트 (패딩 제거된 핵심 메시지에서 ID 부분 제외)
                # core_message_bytes_for_log가 "ID:메시지" 전체이므로, 여기서 ID: 부분을 잘라내면 메시지 텍스트 바이트.
                original_message_text_bytes = core_message_bytes_for_log[id_prefix_len_in_bytes:]

                if original_message_text_bytes: # 실제 메시지 내용이 있는 경우
                    attacked_message_text_bytes = original_message_text_bytes # 복사본으로 작업

                    if current_attack_mode == "modify":
                        temp_message_text_list = bytearray(attacked_message_text_bytes)
                        if temp_message_text_list: # 비어있지 않으면
                            temp_message_text_list[0] = temp_message_text_list[0] ^ 0x01 # 첫 바이트 LSB 반전
                            attacked_message_text_bytes = bytes(temp_message_text_list)
                            print(f"[ATTACK][test1.py] 'modify': Flipped LSB of the first byte of MessageText.")
                        else:
                            print(f"[ATTACK][test1.py] 'modify': MessageText part is empty, no modification.")
                    
                    elif current_attack_mode == "noise":
                        # 메시지 텍스트 부분에만 비트 오류 주입 (예: 5% 오류율)
                        attacked_message_text_bytes = apply_payload_bit_errors(attacked_message_text_bytes, 0.05)
                        print(f"[ATTACK][test1.py] 'noise': Applied ~5% bit errors to MessageText part.")

                    elif current_attack_mode == "jamming":
                        # 메시지 텍스트 부분에만 비트 오류 주입 (예: 30% 오류율)
                        attacked_message_text_bytes = apply_payload_bit_errors(attacked_message_text_bytes, 0.30)
                        print(f"[ATTACK][test1.py] 'jamming': Applied ~30% bit errors to MessageText part.")

                    # 공격 적용된 메시지 텍스트를 원래 패킷 위치에 다시 삽입
                    # data_to_transmit_attacked의 해당 부분을 교체
                    # 주의: attacked_message_text_bytes의 길이가 original_message_text_bytes와 같아야 함 (apply_payload_bit_errors는 길이 유지)
                    if len(attacked_message_text_bytes) == len(original_message_text_bytes):
                        for i in range(len(attacked_message_text_bytes)):
                            if message_text_absolute_start_offset + i < len(data_to_transmit_attacked):
                                data_to_transmit_attacked[message_text_absolute_start_offset + i] = attacked_message_text_bytes[i]
                    else: # 비트오류 주입 함수가 길이를 변경한 경우 (현재는 아님)
                         print(f"[ERROR] Length mismatch after applying bit errors to MessageText. Attack not fully applied to packet.")
                else:
                    print(f"[ATTACK][test1.py] MessageText part is empty. No data-content attack applied.")
            else:
                print(f"[ATTACK][test1.py] Cannot apply payload-specific attack for ID '{final_log_id_for_csv}' due to parsing issues or empty text. Skipping data-content attack.")
        
        # RF 레벨의 노이즈/재밍은 여기서 GMSK 변조 후 샘플에 추가하는 것이 더 현실적이나,
        # 사용자 요청은 "페이로드 부분만 영향"이므로 위에서 비트오류로 처리함.
        # 만약 RF 레벨 공격도 원한다면 아래 로직 활성화. 현재는 비활성화.
        """
        if current_attack_mode == "noise_rf" or current_attack_mode == "jamming_rf":
            # ... GMSK 변조 후 modulated_complex_data_np에 노이즈 추가하는 로직 ...
            pass 
        """

        packet_for_gmsk_payload = bytes(data_to_transmit_attacked)
        packet_to_modulate = GMSK_TX_PREAMBLE + packet_for_gmsk_payload
        
        print(f"[DEBUG] Packet to modulate for test2: {len(GMSK_TX_PREAMBLE)}B GMSK_preamble + {len(packet_for_gmsk_payload)}B (gs_packet_data, possibly attacked) = {len(packet_to_modulate)}B total")

        tb_mod = GMSKModulator(list(packet_to_modulate))
        tb_mod.run()
        
        modulated_complex_data_np = np.array(tb_mod.get_modulated_data(), dtype=np.complex64)
        mod_bytes_to_test2 = modulated_complex_data_np.tobytes()
        
        sock_send_to_test2.sendto(mod_bytes_to_test2, (UDP_IP_SEND_TO_TEST2, UDP_PORT_SEND_TO_TEST2))
        print(f"[test1.py] Sent {len(mod_bytes_to_test2)} GMSK-modulated bytes to test2 ({UDP_IP_SEND_TO_TEST2}:{UDP_PORT_SEND_TO_TEST2}) for ID '{final_log_id_for_csv}'")
        
        t1_processing_seq_count += 1

if __name__ == "__main__":
    main()
