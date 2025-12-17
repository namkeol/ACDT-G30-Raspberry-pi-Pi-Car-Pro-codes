#!/usr/bin/env python3
# body.py
# PiCar-Pro V2 움직임 중심 + 음성인식 통합 코드

import sys
import time
import subprocess

# -----------------------------
# MotorCtrl.py import
# -----------------------------
# MotorCtrl.py 실제 경로 추가
sys.path.append("/home/pi/Adeept_PiCar-Pro-V2/Code/Adeept_PiCar-Pro/Examples/04_Motor")
from MotorCtrl import Motor, motorStop

# -----------------------------
# 기본 이동 함수
# -----------------------------
def forward(t, speed=40):
    Motor(1, 1, speed)
    Motor(2, 1, speed)
    Motor(3, 1, speed)
    Motor(4, 1, speed)
    time.sleep(t)
    motorStop()

def backward(t, speed=40):
    Motor(1, -1, speed)
    Motor(2, -1, speed)
    Motor(3, -1, speed)
    Motor(4, -1, speed)
    time.sleep(t)
    motorStop()

def left_turn(t=1, speed=40):
    Motor(1, -1, speed)
    Motor(2, -1, speed)
    Motor(3, 1, speed)
    Motor(4, 1, speed)
    time.sleep(t)
    motorStop()

def right_turn(t=1, speed=40):
    Motor(1, 1, speed)
    Motor(2, 1, speed)
    Motor(3, -1, speed)
    Motor(4, -1, speed)
    time.sleep(t)
    motorStop()

# -----------------------------
# 음성인식 호출
# -----------------------------
def run_voice_recognition():
    """
    stt_venv 가상환경 활성화 후 음성인식 실행
    """
    subprocess.run(
        ["bash", "-c", "source /home/pi/stt_venv/bin/activate && python3 /home/pi/stt/pi_english_proportion.py"]
    )

# -----------------------------
# 6조 방문 루틴
# -----------------------------
def visit_groups():
    print("조1 이동")
    forward(8)
    run_voice_recognition()

    print("조2 이동")
    right_turn(1)
    forward(3.5)
    run_voice_recognition()

    print("조3 이동")
    forward(3.5)
    run_voice_recognition()

    print("조4 이동")
    right_turn(1)
    forward(8)
    run_voice_recognition()

    print("조5 이동")
    right_turn(1)
    forward(3.5)
    run_voice_recognition()

    print("조6 이동")
    forward(3.5)
    run_voice_recognition()

    print("시작점 복귀")
    right_turn(1)
    forward(8)
    motorStop()

# -----------------------------
# 메인 실행
# -----------------------------
if __name__ == "__main__":
    try:
        visit_groups()
    except KeyboardInterrupt:
        print("\n사용자 중단 - 로봇 정지")
        motorStop()
