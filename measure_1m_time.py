# measure_1m_time.py
# Adeept PiCar-Pro + Raspberry Pi
# 1m 직진 시간 측정용 테스트 코드

import time
from picarpro import car

FORWARD_SPEED = 50   # 원하는 속도(0~100). 테스트 후 조정 가능.

def measure_one_meter(speed=FORWARD_SPEED):
    print("\n==============================")
    print(" 1m 이동 시간 측정 시작 ")
    print("==============================")
    input("로봇을 출발선에 놓고 Enter 키를 누르면 시작합니다...")

    # 로봇 출발
    car.forward(speed)
    start = time.time()
    print("→ 로봇 이동 중…")
    print("1m 지점에 도달하면 Enter 키를 눌러주세요!")

    # 사용자 입력으로 1m 도달 판정
    input()

    end = time.time()
    car.stop()
    duration = end - start

    print(f"\n[결과] 속도 {speed}에서 1m 이동 시간: {duration:.3f}초\n")
    return duration


if __name__ == "__main__":
    try:
        while True:
            t = measure_one_meter()

            # 반복 여부
            again = input("한 번 더 측정할까요? (y/n): ")
            if again.lower() != 'y':
                print("측정 종료.")
                break

    except KeyboardInterrupt:
        print("\n사용자 중지. 로봇 정지.")
        car.stop()
