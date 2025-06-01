#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test1.py: GS(cmdUtil)로부터 수신한 패킷에서 순수 "ID:메시지" 문자열을 추출하여 로깅.
          GroundSystem.py에서 설정한 attack_mode.txt 및 QSettings의 위성/기지국 설정을
          참조하여 공격 강도에 변동을 주어 적용.
          (modify 공격 시 ID 부분은 보호)
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
import random
from PyQt5.QtCore import QSettings # QSettings 임포트

# --- 상수 정의 ---
LISTEN_IP = "0.0.0.0"; LISTEN_PORT = 50000
UDP_IP_SEND_TO_TEST2 = "127.0.0.1"; UDP_PORT_SEND_TO_TEST2 = 8888
ROOTDIR = Path(__file__).resolve().parent
SENT_CSV_PATH = ROOTDIR / "Subsystems" / "cmdGui" / "sample_app_sent.csv"
ATTACK_FILE = ROOTDIR / "attack_mode.txt"
GMSK_TX_PREAMBLE = b'\xAA\xAA'

CMDUTIL_CCSDS_PRI_HDR_LEN = 6
CMDUTIL_INTERNAL_HDR_LEN = 2
CMDUTIL_STRING_FIELD_LEN = 128

# QSettings 이름 (GroundSystem.py와 일치해야 함)
ORGANIZATION_NAME = "MySatComProject"
APPLICATION_NAME = "GroundSystemGUI"

# --- 기본 설정값 (QSettings에서 못 읽어올 경우 사용) ---
DEFAULT_SAT_PARAMS = {
    "sat_type": "소형 위성", "sat_size": 10.0, "sat_speed": 0.05, 
    "orbital_radius": 300.0, "inclination": 45.0, "eccentricity": 0.0,
    "frequency": 2.4, "antenna_gain": 10.0, "transmit_power": 0.0 
}
DEFAULT_GS_PARAMS = {
    "gs_name": "Default GS", "gs_latitude": 37.5665, "gs_longitude": 126.9780, 
    "gs_altitude": 30.0, "min_elevation": 5.0, "gs_antenna_gain": 35.0
}

# --- 클래스 및 함수 정의 (GMSKModulator, get_attack_mode 등은 이전과 동일) ---
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

def apply_payload_bit_errors(payload_bytes: bytes, error_rate: float) -> bytes:
    if not payload_bytes or error_rate == 0: return payload_bytes
    bits = []
    for byte_val in payload_bytes: # 변수명 변경 (byte는 내장 함수)
        for i in range(8): bits.append((byte_val >> (7 - i)) & 1)
    num_bits_to_flip = int(len(bits) * error_rate)
    if num_bits_to_flip == 0 and error_rate > 0 and len(bits) > 0: num_bits_to_flip = 1
    indices_to_flip = random.sample(range(len(bits)), min(num_bits_to_flip, len(bits)))
    for idx in indices_to_flip: bits[idx] = 1 - bits[idx]
    new_bytes = bytearray()
    for i in range(0, len(bits), 8):
        byte_val_res = 0
        for j in range(8):
            if (i + j) < len(bits): byte_val_res = (byte_val_res << 1) | bits[i+j]
        new_bytes.append(byte_val_res)
    return bytes(new_bytes)

# --- 설정 로드 및 LQF 계산 함수 ---
def load_sim_parameters():
    settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
    sat_params = settings.value("satellite/params", defaultValue=DEFAULT_SAT_PARAMS, type=dict)
    gs_params = settings.value("basestation/params", defaultValue=DEFAULT_GS_PARAMS, type=dict)
    return sat_params, gs_params

def calculate_lqf(sat_params, gs_params):
    """ 위성/기지국 설정 기반으로 단순 링크 품질 지수 (0.1 ~ 1.0) 계산 """
    lqf = 1.0
    
    # 위성 송신 전력 (dBm)
    tx_power = sat_params.get("transmit_power", DEFAULT_SAT_PARAMS["transmit_power"])
    if tx_power < -10: lqf -= 0.2 # 매우 낮음
    elif tx_power < 0: lqf -= 0.1   # 낮음

    # 위성 안테나 이득 (dBi)
    sat_gain = sat_params.get("antenna_gain", DEFAULT_SAT_PARAMS["antenna_gain"])
    if sat_gain < 5: lqf -= 0.15
    elif sat_gain < 10: lqf -= 0.05
    
    # 기지국 안테나 이득 (dBi)
    gs_gain = gs_params.get("gs_antenna_gain", DEFAULT_GS_PARAMS["gs_antenna_gain"])
    if gs_gain < 20: lqf -= 0.15
    elif gs_gain < 30: lqf -= 0.05

    # 궤도 반지름 (단위, 거리 프록시)
    radius = sat_params.get("orbital_radius", DEFAULT_SAT_PARAMS["orbital_radius"])
    if radius > 450: lqf -= 0.2 # 매우 멈
    elif radius > 350: lqf -= 0.1 # 멈

    # 주파수 (GHz) - 매우 단순화된 가정: 높을수록 감쇠 약간 더 고려
    freq = sat_params.get("frequency", DEFAULT_SAT_PARAMS["frequency"])
    if freq > 8: lqf -= 0.1 # X-band 이상
    elif freq > 4: lqf -= 0.05 # C-band 이상

    return max(0.1, min(1.0, lqf)) # 0.1 ~ 1.0 사이로 제한

# --- main 함수 ---
def main():
    sock_recv_from_gs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_recv_from_gs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_recv_from_gs.bind((LISTEN_IP, LISTEN_PORT))
    print(f"[test1.py] Listening for packets from GS (via cmdUtil) on UDP {LISTEN_IP}:{LISTEN_PORT} ...")
    print(f"[test1.py] Attack mode file: {ATTACK_FILE.resolve()}")

    sock_send_to_test2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    t1_processing_seq_count = 0

    # 애플리케이션 시작 시 한 번 설정 로드 (또는 주기적 업데이트 가능)
    current_sat_params, current_gs_params = load_sim_parameters()
    print(f"[INFO] Initial Satellite Params: {current_sat_params}")
    print(f"[INFO] Initial Ground Station Params: {current_gs_params}")

    while True:
        gs_packet_data_original, gs_addr = sock_recv_from_gs.recvfrom(4096)
        print(f"\n[test1.py] Received {len(gs_packet_data_original)} bytes of packet data from GS ({gs_addr})")
        
        # 매번 공격 모드 및 LQF 업데이트 (설정이 동적으로 바뀔 수 있으므로)
        current_attack_mode = get_attack_mode()
        # TODO: QSettings 변경 감지 로직이 없다면, load_sim_params()도 루프 내에서 호출하거나,
        # GroundSystem.py가 설정을 변경할 때 test1.py에 알리는 메커니즘 필요.
        # 여기서는 일단 시작 시 로드한 값을 사용. 실시간 반영 원하면 아래 주석 해제.
        # current_sat_params, current_gs_params = load_sim_parameters() 
        lqf = calculate_lqf(current_sat_params, current_gs_params)
        print(f"[INFO] Current Attack Mode: {current_attack_mode}, Calculated LQF: {lqf:.2f}")

        # --- 핵심 "ID:메시지" 문자열 추출 (로깅용, 공격 전 원본 기준) ---
        # (이전 답변의 파싱 로직과 동일)
        core_message_bytes_for_log = b""
        parsed_numeric_id_from_gui = None
        text_repr_for_csv = "[CoreMsgParseError]"
        id_part_str_for_attack_handling = "" 
        fallback_log_id_str = f"T1_ProcSeq_{t1_processing_seq_count}" 
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
                    id_part_str_for_attack_handling = id_str_from_gui
                    text_repr_for_csv = parts[1].strip()
                    try: parsed_numeric_id_from_gui = int(id_str_from_gui)
                    except ValueError: text_repr_for_csv = decoded_core_message_str 
                elif decoded_core_message_str: text_repr_for_csv = decoded_core_message_str.strip()
                else: text_repr_for_csv = "[EmptyCoreMessage]"; core_message_bytes_for_log = b""
            except Exception as e: text_repr_for_csv = "[CoreMsgParseFail]"; core_message_bytes_for_log = b"" 
        else: 
            text_repr_for_csv = gs_packet_data_original.hex() if gs_packet_data_original else "[EmptyGSPacket]"
            core_message_bytes_for_log = b""

        core_message_bits_for_log = bytes_to_bitstring(core_message_bytes_for_log)
        final_log_id_for_csv = parsed_numeric_id_from_gui if parsed_numeric_id_from_gui is not None else fallback_log_id_str
        timestamp_str = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        log_to_sent_csv(final_log_id_for_csv, timestamp_str, text_repr_for_csv, core_message_bits_for_log, current_attack_mode)

        # --- 공격 적용 (LQF 기반 강도 조절) ---
        data_to_transmit_attacked = bytearray(gs_packet_data_original) 

        if current_attack_mode == "drop":
            # LQF에 따른 드랍 확률 (예시: LQF 낮을수록 드랍 확률 증가)
            # drop_chance = (1.0 - lqf) * 0.5 # 예: LQF 0.1이면 45% 드랍, LQF 1.0이면 0% 드랍
            # if random.random() < drop_chance:
            # 여기서는 "drop" 모드 시 항상 드랍으로 유지
            print(f"[ATTACK][test1.py] Dropping packet for ID '{final_log_id_for_csv}' due to 'drop' mode.")
            t1_processing_seq_count += 1; continue 
        
        # "ID:메시지"의 "메시지" 부분에만 공격 적용 준비
        message_text_bytes_to_attack = b""
        message_text_absolute_start_offset = -1

        if id_part_str_for_attack_handling and text_repr_for_csv not in ["[CoreMsgParseError]", "[CoreMsgParseFail]", "[EmptyCoreMessage]", gs_packet_data_original.hex()]:
            id_prefix_str = f"{id_part_str_for_attack_handling}:"
            id_prefix_bytes = id_prefix_str.encode('utf-8')
            id_prefix_len_in_bytes = len(id_prefix_bytes)
            
            # core_message_bytes_for_log가 "ID:메시지" 전체 (패딩 제거) 이므로, 여기서 메시지 부분 추출
            message_text_bytes_to_attack = core_message_bytes_for_log[id_prefix_len_in_bytes:]
            message_text_absolute_start_offset = expected_min_len_for_string_field + id_prefix_len_in_bytes
        
        if message_text_bytes_to_attack: # 실제 메시지 내용이 있을 때만 내용 공격
            attacked_message_text_bytes = message_text_bytes_to_attack # 복사본으로 시작

            if current_attack_mode == "modify":
                # LQF 낮을수록 더 많은 바이트 변경 시도 (최대 3바이트 예시)
                num_bytes_to_change = min(len(attacked_message_text_bytes), round(1 + (1.0 - lqf) * 2))
                temp_message_list = bytearray(attacked_message_text_bytes)
                
                indices_to_change = random.sample(range(len(temp_message_list)), min(num_bytes_to_change, len(temp_message_list)))
                for idx_in_text in indices_to_change:
                    temp_message_list[idx_in_text] = temp_message_list[idx_in_text] ^ random.randint(1,255) # 랜덤 XOR
                attacked_message_text_bytes = bytes(temp_message_list)
                print(f"[ATTACK][test1.py] 'modify' (LQF:{lqf:.2f}): Changed {len(indices_to_change)} byte(s) in MessageText.")
            
            elif current_attack_mode == "noise":
                # LQF 낮을수록 비트 에러율 증가 (1% ~ 10% 예시)
                error_rate = 0.01 + (1.0 - lqf) * 0.09 
                attacked_message_text_bytes = apply_payload_bit_errors(attacked_message_text_bytes, error_rate)
                print(f"[ATTACK][test1.py] 'noise' (LQF:{lqf:.2f}): Applied ~{error_rate*100:.1f}% bit errors to MessageText.")

            elif current_attack_mode == "jamming":
                # LQF 낮을수록 비트 에러율 증가 (10% ~ 50% 예시)
                error_rate = 0.10 + (1.0 - lqf) * 0.40
                attacked_message_text_bytes = apply_payload_bit_errors(attacked_message_text_bytes, error_rate)
                print(f"[ATTACK][test1.py] 'jamming' (LQF:{lqf:.2f}): Applied ~{error_rate*100:.1f}% bit errors to MessageText.")

            # 공격 적용된 메시지 텍스트를 data_to_transmit_attacked에 반영
            if len(attacked_message_text_bytes) == len(message_text_bytes_to_attack):
                for i in range(len(attacked_message_text_bytes)):
                    if message_text_absolute_start_offset + i < len(data_to_transmit_attacked):
                        data_to_transmit_attacked[message_text_absolute_start_offset + i] = attacked_message_text_bytes[i]
            else:
                print(f"[ERROR] ATTACK: Length mismatch after applying bit errors. Original text len: {len(message_text_bytes_to_attack)}, Attacked text len: {len(attacked_message_text_bytes)}")
        elif current_attack_mode in ["modify", "noise", "jamming"]: # 메시지 내용 없거나 파싱 실패
             print(f"[ATTACK][test1.py] No valid MessageText to apply '{current_attack_mode}' attack for ID '{final_log_id_for_csv}'.")


        # --- GMSK 변조 및 전송 ---
        packet_for_gmsk_payload = bytes(data_to_transmit_attacked)
        packet_to_modulate = GMSK_TX_PREAMBLE + packet_for_gmsk_payload
        print(f"[DEBUG] Packet to modulate for test2: {len(GMSK_TX_PREAMBLE)}B GMSK_pre + {len(packet_for_gmsk_payload)}B (gs_pkt, attacked) = {len(packet_to_modulate)}B")

        tb_mod = GMSKModulator(list(packet_to_modulate))
        tb_mod.run()
        mod_bytes_to_test2 = np.array(tb_mod.get_modulated_data(), dtype=np.complex64).tobytes()
        
        sock_send_to_test2.sendto(mod_bytes_to_test2, (UDP_IP_SEND_TO_TEST2, UDP_PORT_SEND_TO_TEST2))
        print(f"[test1.py] Sent {len(mod_bytes_to_test2)} GMSK bytes to test2 for ID '{final_log_id_for_csv}'")
        
        t1_processing_seq_count += 1

if __name__ == "__main__":
    # QApplication 인스턴스가 QSettings 사용 전에 필요할 수 있으므로,
    # main 함수 시작 부분에서 QSettings를 사용한다면 QApplication도 더 일찍 초기화 필요.
    # 여기서는 load_sim_parameters가 QSettings를 사용하므로, app 선언을 더 위로 올리거나,
    # QSettings 호출을 main 함수 안으로 이동. 여기서는 main 함수 안으로 이동.
    
    # from PyQt5.QtWidgets import QApplication # QApplication 임포트 확인
    # app = QApplication(sys.argv) # QSettings 사용 전 QApplication 인스턴스 생성 (필요한 경우)
    # QApplication.setOrganizationName(ORGANIZATION_NAME)
    # QApplication.setApplicationName(APPLICATION_NAME)
    
    main()
