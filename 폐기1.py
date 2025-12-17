import os
import time
import re
import subprocess
from pathlib import Path

from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import motor, servo
from openai import OpenAI

# =========================================================
# 1) 이동 튜닝
# =========================================================
STEER_CENTER = 112.5
STEER_LEFT   = 80
STEER_RIGHT  = 167

TURN_SEC_LEFT  = 5
TURN_SEC_RIGHT = 0.8

SPEED = 35
FWD_SEC_1CELL = 3.0

# =========================================================
# 2) 경로
# =========================================================
PATH = [(0,0), (1,0), (2,0), (2,1), (1,1), (0,1)]
heading = 0  # 동쪽 시작

# =========================================================
# 3) 오디오 / STT
# =========================================================
ARECORD_DEVICE = "plughw:2,0"
SAMPLE_RATE = 44100
RECORD_SEC = 20
AUDIO_PATH = Path("/home/pi/group.wav")

STT_MODEL = "gpt-4o-mini-transcribe"
EN_THRESHOLD = 0.60

# =========================================================
# 4) PCA9685 주소
# =========================================================
PCA_ADDR_CANDIDATES = [0x5F, 0x40, 0x41, 0x60]

# =========================================================
# 5) 채널
# =========================================================
STEER_CH = 11
HEAD_YAW_CH = 10

ARM_J1_CH = 9
ARM_J2_CH = 8
GRIP_CH   = 7

# =========================================================
# 6) 서보 각도
# =========================================================
ARM1_HOME = 40
ARM2_HOME = 90

ARM1_EXTEND = 145
ARM2_EXTEND = 180

GRIP_CLOSE = 10
GRIP_OPEN  = 60

HEAD_YAW_CENTER = 115
HEAD_YAW_LEFT   = 85
HEAD_YAW_RIGHT  = 145

# =========================================================
# 유틸
# =========================================================
def sp(x: int) -> float:
    return max(0, min(100, x)) / 100.0

def count_lang(text: str):
    en = len(re.findall(r"[A-Za-z]", text))
    ko = len(re.findall(r"[\uAC00-\uD7A3]", text))
    return en, ko

def english_ratio(text: str) -> float:
    en, ko = count_lang(text)
    denom = en + ko
    return (en / denom) if denom > 0 else 0.0

def run(cmd: list[str]):
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# 🔥 서보 천천히 이동
def move_servo_slow(srv, start, end, step=1, delay=0.03):
    if start < end:
        rng = range(start, end + 1, step)
    else:
        rng = range(start, end - 1, -step)

    for a in rng:
        srv.angle = a
        time.sleep(delay)

# =========================================================
# 하드웨어 초기화
# =========================================================
def init_pca():
    i2c = busio.I2C(SCL, SDA)
    last_err = None

    for addr in PCA_ADDR_CANDIDATES:
        try:
            pwm = PCA9685(i2c, address=addr)
            pwm.frequency = 50
            time.sleep(0.2)
            print(f"[OK] PCA9685 addr={hex(addr)}")
            return pwm
        except Exception as e:
            last_err = e

    raise RuntimeError(f"PCA9685 못 잡음: {last_err}")

def make_servo(pwm, ch):
    if ch is None:
        return None
    return servo.Servo(pwm.channels[ch], min_pulse=500, max_pulse=2500)

# =========================================================
# 모터
# =========================================================
M1_IN1, M1_IN2 = 15, 14
M2_IN1, M2_IN2 = 12, 13

def make_motors(pwm):
    m1 = motor.DCMotor(pwm.channels[M1_IN1], pwm.channels[M1_IN2])
    m2 = motor.DCMotor(pwm.channels[M2_IN1], pwm.channels[M2_IN2])
    for m in (m1, m2):
        m.decay_mode = motor.SLOW_DECAY
    return m1, m2

def stop_all(motors):
    for m in motors:
        m.throttle = 0

def drive_forward_time(motors, sec, speed=SPEED):
    v = sp(speed)
    for m in motors:
        m.throttle = v
    time.sleep(sec)
    stop_all(motors)

# =========================================================
# 이동
# =========================================================
def steer_to(steer, angle):
    steer.angle = angle
    time.sleep(0.15)

def turn_left_90(motors, steer):
    steer_to(steer, STEER_LEFT)
    drive_forward_time(motors, TURN_SEC_LEFT)
    steer_to(steer, STEER_CENTER)

def turn_right_90(motors, steer):
    steer_to(steer, STEER_RIGHT)
    drive_forward_time(motors, TURN_SEC_RIGHT)
    steer_to(steer, STEER_CENTER)

def forward_cells(motors, n=1):
    drive_forward_time(motors, FWD_SEC_1CELL * n)

def desired_heading(dx, dy):
    if dx == 1 and dy == 0: return 0
    if dx == 0 and dy == 1: return 1
    if dx == -1 and dy == 0: return 2
    if dx == 0 and dy == -1: return 3
    raise ValueError

def rotate_to(target, motors, steer):
    global heading
    diff = (target - heading) % 4
    if diff == 1:
        turn_left_90(motors, steer)
    elif diff == 3:
        turn_right_90(motors, steer)
    elif diff == 2:
        turn_left_90(motors, steer)
        turn_left_90(motors, steer)
    heading = target

# =========================================================
# 녹음 / STT
# =========================================================
def record_wav():
    cmd = [
        "arecord", "-D", ARECORD_DEVICE,
        "-f", "S16_LE", "-r", str(SAMPLE_RATE),
        "-c", "1", "-d", str(RECORD_SEC),
        str(AUDIO_PATH)
    ]
    print("[REC]")
    run(cmd)

def stt_transcribe(client):
    with open(AUDIO_PATH, "rb") as f:
        res = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=f
        )
    return (res.text or "").strip()

# =========================================================
# 동작
# =========================================================
def arm_grip_action(arm1, arm2, grip):
    if grip is None:
        return

    # 홈
    move_servo_slow(arm1, arm1.angle or ARM1_HOME, ARM1_HOME)
    move_servo_slow(arm2, arm2.angle or ARM2_HOME, ARM2_HOME)
    time.sleep(0.2)

    # 🔥 천천히 팔 뻗기
    move_servo_slow(arm1, ARM1_HOME, ARM1_EXTEND, step=1, delay=0.03)
    move_servo_slow(arm2, ARM2_HOME, ARM2_EXTEND, step=1, delay=0.03)

    grip.angle = GRIP_OPEN
    time.sleep(5)
    grip.angle = GRIP_CLOSE
    time.sleep(0.3)

    # 다시 접기
    move_servo_slow(arm1, ARM1_EXTEND, ARM1_HOME, step=1, delay=0.03)
    move_servo_slow(arm2, ARM2_EXTEND, ARM2_HOME, step=1, delay=0.03)

def head_shake_only(head):
    head.angle = HEAD_YAW_CENTER
    for _ in range(2):
        head.angle = HEAD_YAW_LEFT
        time.sleep(0.25)
        head.angle = HEAD_YAW_RIGHT
        time.sleep(0.25)
    head.angle = HEAD_YAW_CENTER

# =========================================================
# 메인
# =========================================================
def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY 없음")

    client = OpenAI()
    pwm = init_pca()
    motors = make_motors(pwm)

    steer = make_servo(pwm, STEER_CH)
    head = make_servo(pwm, HEAD_YAW_CH)
    arm1 = make_servo(pwm, ARM_J1_CH)
    arm2 = make_servo(pwm, ARM_J2_CH)
    grip = make_servo(pwm, GRIP_CH)

    try:
        steer_to(steer, STEER_CENTER)
        stop_all(motors)

        for i, pos in enumerate(PATH):
            print(f"\n[GROUP {i+1}] {pos}")

            if i > 0:
                x0, y0 = PATH[i-1]
                x1, y1 = pos

                if (x0, y0) == (2,0) and (x1, y1) == (2,1):
                    turn_left_90(motors, steer)
                    forward_cells(motors, 1)
                    global heading
                    heading = 2
                else:
                    tgt = desired_heading(x1-x0, y1-y0)
                    rotate_to(tgt, motors, steer)
                    forward_cells(motors, 1)

            record_wav()
            text = stt_transcribe(client)
            ratio = english_ratio(text)

            print(f"[TXT] {text}")
            print(f"[ENGLISH %] {ratio*100:.2f}")

            if ratio >= EN_THRESHOLD:
                arm_grip_action(arm1, arm2, grip)
            else:
                head_shake_only(head)

        print("MISSION COMPLETE")

    finally:
        stop_all(motors)
        pwm.deinit()

if __name__ == "__main__":
    main()
