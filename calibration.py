#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# calibration.py
# PiCar-Pro V2 이동 거리 & 회전 각도 캘리브레이션 (안전 속도 적용)

import sys
import time

# MotorCtrl.py 경로 추가
sys.path.append("/home/pi/Adeept_PiCar-Pro-V2/Code/Adeept_PiCar-Pro/Examples/04_Motor")
from MotorCtrl import Motor, motorStop

# -----------------------------
# 이동 함수 (속도 안전하게 30으로 조정)
# -----------------------------
def forward(t, speed=30):
    Motor(1, 1, speed)
    Motor(2, 1, speed)
    Motor(3, 1, speed)
    Motor(4, 1, speed)
    time.sleep(t)
    motorStop()
    time.sleep(0.5)  # 모터 과부하 방지

def backward(t, speed=30):
    Motor(1, -1, speed)
    Motor(2, -1, speed)
    Motor(3, -1, speed)
    Motor(4, -1, speed)
    time.sleep(t)
    motorStop()
    time.sleep(0.5)

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
# 캘리브레이션 루틴
# -----------------------------
def calibration_routine():
    print("===== 안전 캘리브레이션 시작 =====")
    print("각 단계마다 로봇을 관찰하고 거리를 측정하세요")
    input("준비되면 Enter를 눌러 시작")

    # 1m 전진 테스트 (약 2초)
    print("\n1m 전진 테스트")
    start = time.time()
    forward(2.0)
    end = time.time()
    print(f"실제 1m 전진 시간: {end-start:.2f}초")
    
    # 1m 후진 테스트
    print("\n1m 후진 테스트")
    start = time.time()
    backward(2.0)
    end = time.time()
    print(f"실제 1m 후진 시간: {end-start:.2f}초")

    # 90도 회전 테스트
    print("\n90도 우회전 테스트")
    start = time.time()
    right_turn(1.0)
    end = time.time()
    print(f"실제 90도 우회전 시간: {end-start:.2f}초")

    print("\n90도 좌회전 테스트")
    start = time.time()
    left_turn(1.0)
    end = time.time()
    print(f"실제 90도 좌회전 시간: {end-start:.2f}초")

    print("\n===== 캘리브레이션 완료 =====")
    print("측정한 시간을 main_safe.py forward/turn 함수에 반영하세요")

# -----------------------------
# 메인 실행
# -----------------------------
if __name__ == "__main__":
    try:
        calibration_routine()
    except KeyboardInterrupt:
        print("\n사용자 중단 - 로봇 정지")
        motorStop()
