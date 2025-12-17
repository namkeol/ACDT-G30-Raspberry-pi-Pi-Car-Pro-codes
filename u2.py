import time
from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import motor, servo

# =========================
# 튜닝 값
# =========================
STEER_CENTER = 112
STEER_LEFT   = 80

SPEED = 23.6
UTURN_SEC   = 8.5    # ⭐ 반원 시간
REVERSE_SEC = 1.0    # ⭐ 후진 시간

# =========================
# 채널 설정
# =========================
STEER_CH = 11

M1_IN1, M1_IN2 = 15, 14
M2_IN1, M2_IN2 = 12, 13

# =========================
# 공통 유틸
# =========================
def sp(x):
    return max(0, min(100, x)) / 100.0

def stop_all(motors):
    for m in motors:
        m.throttle = 0

def drive(motors, speed):
    v = sp(speed)
    for m in motors:
        m.throttle = v

# =========================
# 초기화 (주소 0x5F 고정)
# =========================
def init():
    i2c = busio.I2C(SCL, SDA)

    pwm = PCA9685(i2c, address=0x5F)
    pwm.frequency = 50
    print("[OK] PCA9685 @ 0x5F")

    steer = servo.Servo(
        pwm.channels[STEER_CH],
        min_pulse=500,
        max_pulse=2500
    )

    m1 = motor.DCMotor(pwm.channels[M1_IN1], pwm.channels[M1_IN2])
    m2 = motor.DCMotor(pwm.channels[M2_IN1], pwm.channels[M2_IN2])
    for m in (m1, m2):
        m.decay_mode = motor.SLOW_DECAY

    return pwm, steer, (m1, m2)

# =========================
# 🔥 3 → 4 유턴 (반원 + 핸들 중앙 + 후진)
# =========================
def uturn_half_circle(motors, steer):
    print("[UTURN] start")

    # 1. left steering
    steer.angle = STEER_LEFT
    time.sleep(0.2)

    # 2. forward, half circle
    drive(motors, SPEED)
    time.sleep(UTURN_SEC)

    # 3. stop
    stop_all(motors)
    time.sleep(0.2)

    # 4. steer_center
    steer.angle = STEER_CENTER
    time.sleep(0.2)

    # 5. backward
    v = -sp(SPEED)
    for m in motors:
        m.throttle = v
    time.sleep(REVERSE_SEC)
    stop_all(motors)

    print("[UTURN] done (angle OK, position fixed)")

# =========================
# 메인
# =========================
def main():
    pwm, steer, motors = init()

    try:
        steer.angle = STEER_CENTER
        stop_all(motors)
        time.sleep(1)

        print("=== 3 → 4 U-TURN TEST ===")
        uturn_half_circle(motors, steer)

        print("TEST END")

    finally:
        stop_all(motors)
        pwm.deinit()

if __name__ == "__main__":
    main()
