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
# 1) 이동 튜닝 (✅ 통일)
# =========================================================
STEER_CENTER = 112
STEER_CENTER_UTURN = 112
STEER_LEFT   = 80
STEER_RIGHT  = 167

TURN_SEC_LEFT  = 5
TURN_SEC_RIGHT = 0.8

SPEED = 23.6
FWD_SEC_1CELL = 3.6

# =========================================================
# 2) 그룹/경로
# =========================================================
PATH = [(0,0), (1,0), (2,0), (2,1), (1,1), (0,1)]
heading = 0  # 동쪽 시작

# =========================================================
# 3) 오디오 / STT
# =========================================================
ARECORD_DEVICE = "plughw:2,0"
SAMPLE_RATE = 44100
RECORD_SEC = 10
AUDIO_PATH = Path("/home/pi/group.wav")

STT_MODEL = "gpt-4o-mini-transcribe"
EN_THRESHOLD = 0.60

# =========================================================
# 4) PCA9685 주소
# =========================================================
PCA_ADDR_CANDIDATES = [0x5F, 0x40, 0x41, 0x60]

# =========================================================
# 5) 서보 채널
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
GRIP_OPEN  = 85

HEAD_YAW_CENTER = 115
HEAD_YAW_LEFT   = 85
HEAD_YAW_RIGHT  = 145

# =========================================================
# 내부 유틸
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
            print(f"[OK] PCA9685 addr = {hex(addr)}")
            return pwm
        except Exception as e:
            last_err = e
    raise RuntimeError(f"PCA9685 못 잡음: {last_err}")

def make_servo(pwm, ch):
    return servo.Servo(pwm.channels[ch], min_pulse=500, max_pulse=2500)

# =========================================================
# 모터 / 조향
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
# U-TURN
# =========================================================
UTURN_SEC   = 7.1
REVERSE_SEC = 1.0

def uturn_half_circle(motors, steer_srv):
    print("[UTURN] start (3 -> 4)")
    steer_srv.angle = STEER_LEFT
    time.sleep(0.2)

    v = sp(SPEED)
    for m in motors:
        m.throttle = v
    time.sleep(UTURN_SEC)
    stop_all(motors)

    time.sleep(0.2)
    steer_srv.angle = STEER_CENTER_UTURN
    time.sleep(0.2)

    for m in motors:
        m.throttle = -v
    time.sleep(REVERSE_SEC)
    stop_all(motors)

    print("[UTURN] done")

# =========================================================
# 회전 / 직진
# =========================================================
def steer_to(steer_srv, angle):
    steer_srv.angle = angle
    time.sleep(0.15)

def turn_left_90(motors, steer_srv):
    steer_to(steer_srv, STEER_LEFT)
    drive_forward_time(motors, TURN_SEC_LEFT, SPEED)
    steer_to(steer_srv, STEER_CENTER)

def turn_right_90(motors, steer_srv):
    steer_to(steer_srv, STEER_RIGHT)
    drive_forward_time(motors, TURN_SEC_RIGHT, SPEED)
    steer_to(steer_srv, STEER_CENTER)

def forward_cells(motors, steer_srv, n=1):
    steer_to(steer_srv, STEER_CENTER)
    drive_forward_time(motors, FWD_SEC_1CELL * n, SPEED)

def desired_heading(dx, dy):
    if dx == 1 and dy == 0:  return 0
    if dx == 0 and dy == 1:  return 1
    if dx == -1 and dy == 0: return 2
    if dx == 0 and dy == -1: return 3
    raise ValueError

def rotate_to(target, motors, steer_srv):
    global heading
    diff = (target - heading) % 4
    if diff == 0:
        return
    if diff == 1:
        turn_left_90(motors, steer_srv)
    elif diff == 3:
        turn_right_90(motors, steer_srv)
    elif diff == 2:
        turn_left_90(motors, steer_srv)
        turn_left_90(motors, steer_srv)
    heading = target

# =========================================================
# 녹음 / STT (📌 출력만 추가)
# =========================================================
def record_wav():
    print(f"[REC] START recording ({RECORD_SEC}s)")

    cmd = [
        "arecord",
        "-D", ARECORD_DEVICE,
        "-f", "S16_LE",
        "-r", str(SAMPLE_RATE),
        "-c", "1",
        str(AUDIO_PATH),
    ]

    proc = subprocess.Popen(cmd)

    for i in range(1, RECORD_SEC + 1):
        print(f"[REC] {i} / {RECORD_SEC} sec")
        time.sleep(1)

    proc.terminate()
    proc.wait()

    print("[REC] END recording")

def stt_transcribe(client):
    print("[STT] processing...")
    if not AUDIO_PATH.exists():
        print("[STT] done (no audio)")
        return ""
    with open(AUDIO_PATH, "rb") as f:
        res = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=f,
        )
    print("[STT] done")
    return (res.text or "").strip()

# =========================================================
# 동작
# =========================================================
def arm_grip_action(a1, a2, g):
    a1.angle = ARM1_HOME
    a2.angle = ARM2_HOME
    time.sleep(0.3)

    step, delay = 2, 0.03
    max_steps = max(ARM1_EXTEND - ARM1_HOME, ARM2_EXTEND - ARM2_HOME)

    for i in range(0, max_steps + 1, step):
        a1.angle = min(ARM1_HOME + i, ARM1_EXTEND)
        a2.angle = min(ARM2_HOME + i, ARM2_EXTEND)
        time.sleep(delay)

    g.angle = GRIP_OPEN
    time.sleep(1)
    g.angle = GRIP_CLOSE
    time.sleep(0.5)

    a1.angle = ARM1_HOME
    a2.angle = ARM2_HOME

def head_shake(head):
    head.angle = HEAD_YAW_CENTER
    time.sleep(0.3)
    for _ in range(2):
        head.angle = HEAD_YAW_LEFT
        time.sleep(0.4)
        head.angle = HEAD_YAW_RIGHT
        time.sleep(0.4)
    head.angle = HEAD_YAW_CENTER

# =========================================================
# MAIN
# =========================================================
def main():
    client = OpenAI()
    pwm = init_pca()
    motors = make_motors(pwm)

    steer = make_servo(pwm, STEER_CH)
    head  = make_servo(pwm, HEAD_YAW_CH)
    arm1  = make_servo(pwm, ARM_J1_CH)
    arm2  = make_servo(pwm, ARM_J2_CH)
    grip  = make_servo(pwm, GRIP_CH)

    try:
        steer_to(steer, STEER_CENTER)
        stop_all(motors)

        for idx, pos in enumerate(PATH):
            print(f"\n========== GROUP {idx+1} ==========")

            if idx > 0:
                x0, y0 = PATH[idx-1]
                x1, y1 = pos

                if (x0, y0) == (2, 0) and (x1, y1) == (2, 1):
                    uturn_half_circle(motors, steer)
                    global heading
                    heading = 2
                else:
                    dx, dy = x1 - x0, y1 - y0
                    rotate_to(desired_heading(dx, dy), motors, steer)
                    forward_cells(motors, steer, 1)

            record_wav()
            text = stt_transcribe(client)

            ratio = english_ratio(text)
            print(f"[TXT] {text}")
            print(f"[RATIO] {ratio*100:.1f}%")

            if ratio >= EN_THRESHOLD:
                arm_grip_action(arm1, arm2, grip)
            else:
                head_shake(head)

        print("\n=== MISSION COMPLETE ===")

    finally:
        stop_all(motors)
        pwm.deinit()

if __name__ == "__main__":
    main()
