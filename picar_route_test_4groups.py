# picar_route_test_4groups.py
# Adeept PiCar-Pro + Raspberry Pi 5
# 테스트용 소형 직사각형 방(3m x 2m) 외곽 주행 + 4개 지점 정지 루프

import sys
sys.path.append("/home/pi/Adeept_PiCar-Pro")

import time
import subprocess
from picarpro import car

# ======== 테스트용 설정값 ========
FORWARD_SPEED = 40     # 테스트용 속도 약하게
TURN_SPEED = 35
STOP_TIME = 1
LOOP_DELAY = 1

# ======== 축소된 방 크기 (단위: m) ========
ROOM_WIDTH  = 3.0     # 원래 13m → 테스트용 3m
ROOM_HEIGHT = 2.0     # 원래 7.3m → 테스트용 2m

# 4개 조 위치
group_positions = [
    "Group 1",   # 1번째 변 끝
    "Group 2",   # 2번째 변 끝
    "Group 3",   # 3번째 변 끝
    "Group 4"    # 4번째 변 끝
]

# =====================
# 기본 이동 함수
# =====================

def go_forward(duration, speed=FORWARD_SPEED):
    car.forward(speed)
    time.sleep(duration)
    car.stop()

def turn_left(duration, speed=TURN_SPEED):
    car.turn_left(speed)
    time.sleep(duration)
    car.stop()

# =====================
# 거리 → 시간 변환
# =====================

# ★ 테스트 환경에서는 더 느릴 수 있으므로 0.20 m/s로 가정
ROBOT_SPEED_MPS = 0.20

def meters_to_seconds(distance_m):
    return distance_m / ROBOT_SPEED_MPS

# =====================
# 외부 스크립트 실행 (가상환경 사용)
# =====================

def run_stt_script():
    script_path = "/home/pi/stt/pi_english_proportion.py"
    venv_python = "/home/pi/stt_venv/bin/python"

    print(f"▶ 외부 스크립트 실행 (venv): {script_path}")

    try:
        subprocess.run([venv_python, script_path], check=True)
        print("▶ 외부 스크립트 실행 완료\n")
    except Exception as e:
        print(f"⚠ 외부 스크립트 실행 중 오류 발생: {e}\n")

# =====================
# 방문 처리
# =====================

def visit_group(name):
    print(f"▶ {name} 위치 도달 — 정지 중...")
    car.stop()
    time.sleep(STOP_TIME)

    run_stt_script()

    print(f"▶ {name} 방문 완료\n")

# =====================
# 한바퀴 루틴 (4개 구간)
# =====================

def run_one_lap():
    print("===== 테스트 한바퀴 시작 =====")

    # 4개 조 → 각각 변 하나씩 담당
    segment_lengths = [
        ROOM_WIDTH,    # Group 1까지
        ROOM_HEIGHT,   # Group 2까지
        ROOM_WIDTH,    # Group 3까지
        ROOM_HEIGHT    # Group 4까지
    ]

    for i in range(4):
        segment = segment_lengths[i]
        travel_time = meters_to_seconds(segment)

        print(f"→ {group_positions[i]}로 이동 중... ({segment:.2f}m)")
        go_forward(travel_time)

        visit_group(group_positions[i])

        # 네 변 중 마지막 변(4번째)을 제외한 나머지는 회전
        if i < 3:
            print("↪ 90도 좌회전")
            turn_left(0.7)  # 테스트 환경에 맞게 작은 회전값
        else:
            print("※ 마지막 구간 — 회전 없음")

    print("===== 테스트 한바퀴 종료 =====\n")

# =====================
# 메인 루프
# =====================

if __name__ == "__main__":
    try:
        while True:
            run_one_lap()
            print(f"{LOOP_DELAY}초 대기 후 반복...")
            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("프로그램 종료.")
        car.stop()
