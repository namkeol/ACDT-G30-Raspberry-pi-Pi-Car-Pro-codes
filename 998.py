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
STEER_CENTER = 112        # 일반 주행용
STEER_CENTER_UTURN = 112  # U-turn 전용
STEER_LEFT   = 80
STEER_RIGHT  = 167

TURN_SEC_LEFT  = 5
TURN_SEC_RIGHT = 0.8

SPEED = 23.6            # 0-100
FWD_SEC_1CELL = 3.6   # 30cm(1칸) 시간

# =========================================================
# 2) 그룹/경로
# =========================================================
PATH = [(0,0), (1,0), (2,0), (2,1), (1,1), (0,1)]
heading = 0  # 시작은 동쪽(+x)

# =========================================================
# 3) 오디오/STT
# =========================================================
ARECORD_DEVICE = "plughw:2,0"  # card2, device0
SAMPLE_RATE = 44100
RECORD_SEC = 20
AUDIO_PATH = Path("/home/pi/group.wav")

STT_MODEL = "gpt-4o-mini-transcribe"
EN_THRESHOLD = 0.60

# =========================================================
# 4) PCA9685 주소 후보
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
# 6) 서보 각도 튜닝
# =========================================================
ARM1_HOME = 40
ARM2_HOME = 90

GRIP_CLOSE = 10
GRIP_OPEN  = 85

ARM1_EXTEND = 145
ARM2_EXTEND = 180

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

def run(cmd: list[str]):
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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
            continue
    raise RuntimeError(f"PCA9685 못 잡음. last_err={last_err}")

def make_servo(pwm, ch: int | None):
    if ch is None:
        return None
    return servo.Servo(pwm.channels[ch], min_pulse=500, max_pulse=2500)

# =========================================================
# 모터/조향 제어
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

def drive_forward_time(motors, sec: float, speed=SPEED):
    v = sp(speed)
    for m in motors:
        m.throttle = v
    time.sleep(sec)
    stop_all(motors)

# =========================================================
# 3 -> 4 유턴 전용
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
    v = -sp(SPEED)
    for m in motors:
        m.throttle = v
    time.sleep(REVERSE_SEC)
    stop_all(motors)
    print("[UTURN] done (arrived at group 4)")

# =========================================================
# 회전/직진
# =========================================================
def steer_to(steer_srv, angle: int):
    steer_srv.angle = angle
    time.sleep(0.15)

def turn_left_90(motors, steer_srv):
    steer_to(steer_srv, STEER_LEFT)
    drive_forward_time(motors, TURN_SEC_LEFT, speed=SPEED)
    steer_to(steer_srv, STEER_CENTER)

def turn_right_90(motors, steer_srv):
    steer_to(steer_srv, STEER_RIGHT)
    drive_forward_time(motors, TURN_SEC_RIGHT, speed=SPEED)
    steer_to(steer_srv, STEER_CENTER)

def forward_cells(motors, steer_srv, n=1):
    steer_to(steer_srv, STEER_CENTER)  # 직진 전 센터
    drive_forward_time(motors, FWD_SEC_1CELL * n, speed=SPEED)

def desired_heading(dx, dy):
    if dx == 1 and dy == 0:  return 0
    if dx == 0 and dy == 1:  return 1
    if dx == -1 and dy == 0: return 2
    if dx == 0 and dy == -1: return 3
    raise ValueError(f"한 번에 1칸 이동만 지원: dx={dx}, dy={dy}")

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
# 녹음 - STT
# =========================================================
def record_wav():
    cmd = [
        "arecord",
        "-D", ARECORD_DEVICE,
        "-f", "S16_LE",
        "-r", str(SAMPLE_RATE),
        "-c", "1",
        "-d", str(RECORD_SEC),
        str(AUDIO_PATH),
    ]
    print(f"[REC] {RECORD_SEC}s -> {AUDIO_PATH}")
    run(cmd)

def stt_transcribe(client: OpenAI) -> str:
    if not AUDIO_PATH.exists():
        return ""
    with open(AUDIO_PATH, "rb") as f:
        res = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=f,
        )
    return (res.text or "").strip()

# =========================================================
# 동작
# =========================================================
def arm_grip_action(arm1, arm2, grip):
    if grip is None:
        print("[WARN] GRIP 서보 없음 - 스킵")
        return

    if arm1 is not None and arm2 is not None:
        arm1.angle = ARM1_HOME
        arm2.angle = ARM2_HOME
        time.sleep(0.2)
        a1_start, a2_start = ARM1_HOME, ARM2_HOME
        a1_end, a2_end = ARM1_EXTEND, ARM2_EXTEND
        step, delay = 2, 0.03
        max_steps = max(abs(a1_end - a1_start), abs(a2_end - a2_start))
        for i in range(0, max_steps + 1, step):
            arm1.angle = min(a1_start + i, a1_end)
            arm2.angle = min(a2_start + i, a2_end)
            time.sleep(delay)

    grip.angle = GRIP_OPEN
    time.sleep(5)
    grip.angle = GRIP_CLOSE
    time.sleep(0.3)

    if arm1 is not None and arm2 is not None:
        arm1.angle = ARM1_HOME
        arm2.angle = ARM2_HOME
        time.sleep(0.5)

def head_shake_smooth(head_yaw):
    if head_yaw is None:
        print("[WARN] HEAD_YAW 서보 없음 - 도리도리 스킵")
        return
    head_yaw.angle = HEAD_YAW_CENTER
    time.sleep(0.3)
    for _ in range(2):
        head_yaw.angle = HEAD_YAW_LEFT + 10
        time.sleep(0.5)
        head_yaw.angle = HEAD_YAW_RIGHT - 10
        time.sleep(0.5)
    head_yaw.angle = HEAD_YAW_CENTER
    time.sleep(0.3)

# =========================================================
# 메인
# =========================================================
def main():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수 없음")

    client = OpenAI()
    pwm = init_pca()
    motors = make_motors(pwm)
    steer_srv = make_servo(pwm, STEER_CH)
    if steer_srv is None:
        raise RuntimeError("STEER_CH가 None이면 이동 못 함")

    head_yaw = make_servo(pwm, HEAD_YAW_CH)
    arm1 = make_servo(pwm, ARM_J1_CH)
    arm2 = make_servo(pwm, ARM_J2_CH)
    grip = make_servo(pwm, GRIP_CH)

    try:
        steer_to(steer_srv, STEER_CENTER)
        stop_all(motors)

        print("6 groups start")

        for idx, pos in enumerate(PATH):
            print(f"\n[GROUP {idx+1}/{len(PATH)}] pos={pos}")

            if idx > 0:
                (x0, y0) = PATH[idx-1]
                (x1, y1) = pos

                # U-turn 처리
                if (x0, y0) == (2, 0) and (x1, y1) == (2, 1):
                    print("[MOVE] (2,0)->(2,1): U-turn half circle (3 -> 4)")
                    uturn_half_circle(motors, steer_srv)
                    global heading
                    heading = 2
                else:
                    dx, dy = x1 - x0, y1 - y0
                    tgt = desired_heading(dx, dy)
                    rotate_to(tgt, motors, steer_srv)
                    forward_cells(motors, steer_srv, 1)  # steer_srv 전달

                stop_all(motors)

            record_wav()
            try:
                text = stt_transcribe(client)
            except Exception as e:
                text = ""
                print(f"[STT ERR] {e}")

            ratio = english_ratio(text)
            en, ko = count_lang(text)
            percent = ratio * 100

            print(f"[TXT] {text}")
            print(f"[RATIO] en={en}, ko={ko}, english_ratio={percent:.3f}%")

            if ratio >= EN_THRESHOLD:
                print(f"[DECISION] English >= {EN_THRESHOLD:.2f}")
                arm_grip_action(arm1, arm2, grip)
            else:
                print(f"[DECISION] English < {EN_THRESHOLD:.2f}")
                head_shake_smooth(head_yaw)

        print("\nmission complete")

    finally:
        stop_all(motors)
        try:
            pwm.deinit()
        except Exception:
            pass

if __name__ == "__main__":
    main()
