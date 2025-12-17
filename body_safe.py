#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main_safe.py
# PiCar-Pro V2 안전 이동 + 음성인식 통합
# 조 이동 순서: 1 → 2 → 3 → 6 → 5 → 4 → 1 (가장자리 루프)

import sys
import time
import subprocess

# MotorCtrl.py 경로 추가
sys.path.append("/home/pi/Adeept_PiCar-Pro-V2/Code/Adeept_PiCar-Pro/Examples/04_Motor")
from MotorCtrl import Motor, motorStop

# -----------------------------
# 이동 함수 (조금 느리게, 안전)
# -----------------------------
def forward(t, speed=30):
    Motor(1, 1, speed)
    Motor(2, 1, speed)
    Motor(3, 1, speed)
    Motor(4, 1, speed)
    time.sleep(t)
    motorStop()
    time.sleep(1)  # 모터 과부하 방지

def backward(t, speed=30):
    Motor(1, -1, speed)
    Motor(2, -1, speed)
    Motor(3, -1, speed)
    Motor(4, -1, speed)
    time.sleep(t)
    motorStop()
    time.sleep(1)

def left_turn(t=1, speed=30):
    Motor(1, -1, speed)
    Motor(2, -1, speed)
    Motor(3, 1, speed)
    Motor(4, 1, speed)
    time.sleep(t)
    motorStop()
    time.sleep(0.5)

def right_turn(t=1, speed=30):
    Motor(1, 1, speed)
    Motor(2, 1, speed)
    Motor(3, -1, speed)
    Motor(4, -1, speed)
    time.sleep(t)
    motorStop()
    time.sleep(0.5)

# -----------------------------
# 안전 음성인식 호출
# -----------------------------
def run_voice_recognition():
    """
    stt_venv 가상환경 활성화 후 음성인식 실행
    subprocess check=True로 완료 후 종료
    """
    try:
        subprocess.run(
            ["bash", "-c", "source /home/pi/stt_venv/bin/activate && python3 /home/pi/stt/pi_english_proportion.py"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"[Warning] 음성인식 실행 오류: {e}")
    time.sleep(1)

# -----------------------------
# 6조 가장자리 루프 이동
# -----------------------------
def visit_groups():
    # 1 → 2 → 3
    print("조1 이동")
    forward(3.5)  # 실제 방 거리 기반 조정 필요
    run_voice_recognition()

    print("조2 이동")
    right_turn(1)
    forward(3.5)
    run_voice_recognition()

    print("조3 이동")
    right_turn(1)
    forward(3.5)
    run_voice_recognition()

    # 3 → 6
    right_turn(1)
    forward(3.5)
    run_voice_recognition()

    # 6 → 5
    right_turn(1)
    forward(3.5)
    run_voice_recognition()

    # 5 → 4
    right_turn(1)
    forward(3.5)
    run_voice_recognition()

    # 4 → 1 (시작점 복귀)
    right_turn(1)
    forward(3.5)
    motorStop()
    print("루프 완료, 시작점 복귀")

# -----------------------------
# 메인 실행
# -----------------------------
if __name__ == "__main__":
    try:
        visit_groups()
    except KeyboardInterrupt:
        print("\n사용자 중단 - 로봇 정지")
        motorStop()
