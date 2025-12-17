# picar_route.py
# Adeept PiCar-Pro + Raspberry Pi 5
# 직사각형 방(13m x 7.3m) 외곽 주행 + 6개 지점 정지 루프

import time
from picarpro import car

# ======== 설정값 ========
FORWARD_SPEED = 50   # 모터 속도(0~100)
TURN_SPEED = 40
STOP_TIME = 2        # 정지 시간(초)
LOOP_DELAY = 1       # 매 루프 사이 잠깐 대기

# 방 크기 (단위: m)
ROOM_WIDTH = 13.0
ROOM_HEIGHT = 7.3

# 6개 조 위치 (예: 방 외곽을 따라 등간격이라고 가정)
# 실제 위치에 맞게 수정 가능
group_positions = [
    "Group 1", 
    "Group 2",
    "Group 3",
    "Group 4",
    "Group 5",
    "Group 6"
]

# =====================
# 기본 이동 함수
# =====================

def go_forward(duration, speed=FORWARD_SPEED):
    car.forward(speed)
    time.sleep(duration)
    car.stop()

def go_backward(duration, speed=FORWARD_SPEED):
    car.backward(speed)
    time.sleep(duration)
    car.stop()

def turn_left(duration, speed=TURN_SPEED):
    car.turn_left(speed)
    time.sleep(duration)
    car.stop()

def turn_right(duration, speed=TURN_SPEED):
    car.turn_right(speed)
    time.sleep(duration)
    car.stop()


# =====================
# 거리를 시간으로 환산 (간단한 기본 모델)
# 실제 주행 속도 측정해서 조정하는 걸 강력 추천
# =====================

# 예: 로봇 속도 = 0.25m/s 라고 가정 (테스트 후 수정)
ROBOT_SPEED_MPS = 0.25  

def meters_to_seconds(distance_m):
    return distance_m / ROBOT_SPEED_MPS


# =====================
# 방문 시 실행할 사용자 정의 함수
# =====================

def visit_group(name):
    print(f"▶ {name} 위치 도달 — 정지 중...")
    car.stop()
    time.sleep(STOP_TIME)

    # ---- 여기에 사용자가 원하는 동작 삽입 가능 ----
    # 예: 사진 촬영, 센서 측정, 네트워크 전송 등
    # custom_function()
    # ----------------------------------------------

    print(f"▶ {name} 방문 완료\n")


# =====================
# 한 바퀴 외곽 주행 루틴
# =====================

def run_one_lap():
    print("===== 한바퀴 시작 =====")

    # 방 길이 방향(13m)에 3개 그룹, 짧은 변(7.3m)에 3개 그룹 배치 예시
    segment_lengths = [
        ROOM_WIDTH / 3,  # G1~G3 위치
        ROOM_WIDTH / 3,
        ROOM_WIDTH / 3,
        ROOM_HEIGHT / 3, # G4~G6 위치
        ROOM_HEIGHT / 3,
        ROOM_HEIGHT / 3,
    ]

    # 6개 각 지점 순차 이동
    for i in range(6):
        segment = segment_lengths[i]
        travel_time = meters_to_seconds(segment)

        # 앞으로 이동
        print(f"→ {group_positions[i]}로 이동 중... ({segment:.2f}m)")
        go_forward(travel_time)

        # 방문 처리
        visit_group(group_positions[i])

        # 다음 방향으로 90도 회전 (모서리 3개 지날 때만)
        if i in [2, 5]:  # 3번째, 6번째 지점에서 큰 회전
            print("↪ 90도 좌회전")
            turn_left(1.0)
        else:
            continue

    print("===== 한바퀴 종료 =====\n")


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
