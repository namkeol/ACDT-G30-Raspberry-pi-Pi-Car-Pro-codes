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
TURN_SEC_90 = 1.0  # 90도 회전 시간
SPEED = 65         # 0-100
FWD_SEC_1CELL = 1.0   # 30cm(1칸) 시간

# =========================================================
# 2) 그룹/경로 (6개 점)
# =========================================================
PATH = [(0,0), (1,0), (2,0), (2,1), (1,1), (0,1)]
heading = 0  # 시작은 동쪽(+x) 가정

# =========================================================
# 3) 오디오/STT
# =========================================================
ARECORD_DEVICE = "plughw:2,0"
SAMPLE_RATE = 44100
RECORD_SEC = 20
AUDIO_PATH = Path("/home/pi/group.wav")
STT_MODEL = "gpt-4o-mini-transcribe"
EN_THRESHOLD = 0.80

# =========================================================
# 4) PCA9685 주소 후보
# =========================================================
PCA_ADDR_CANDIDATES = [0x5F, 0x40, 0x41, 0x60]

# =========================================================
# 5) 서보 채널
# =========================================================
HEAD_YAW_CH = 3        # 도리도리
ARM_J1_CH = 2
ARM_J2_CH = 1
GRIP_CH   = 0

# =========================================================
# 6) 서보 각도
# =========================================================
ARM1_HOME = 40
ARM2_HOME = 90
GRIP_CLOSE = 10
GRIP_OPEN  = 60
ARM1_EXTEND = 160
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
    raise RuntimeError(f"PCA9685 못 잡음. I2C/배선/전원 확인 필요. last_err={last_err}")

def make_servo(pwm, ch: int | None):
    if ch is None:
        return None
    return servo.Servo(pwm.channels[ch], min_pulse=500, max_pulse=2500)

# =========================================================
# 모터
# =========================================================
M1_IN1, M1_IN2 = 15, 14
M2_IN1, M2_IN2 = 12, 13
M3_IN1, M3_IN2 = 11, 10
M4_IN1, M4_IN2 = 8,  9

def make_motors(pwm):
    m1 = motor.DCMotor(pwm.channels[M1_IN1], pwm.channels[M1_IN2])
    m2 = motor.DCMotor(pwm.channels[M2_IN1], pwm.channels[M2_IN2])
    m3 = motor.DCMotor(pwm.channels[M3_IN1], pwm.channels[M3_IN2])
    m4 = motor.DCMotor(pwm.channels[M4_IN1], pwm.channels[M4_IN2])
    for m in (m1, m2, m3, m4):
        m.decay_mode = motor.SLOW_DECAY
    return m1, m2, m3, m4

def stop_all(motors):
    for m in motors:
        m.throttle = 0

# =========================================================
# 이동 (차동구동)
# =========================================================
def forward_time(motors, sec, speed=SPEED):
    v = sp(speed)
    for m in motors:
        m.throttle = v
    time.sleep(sec)
    stop_all(motors)
    time.sleep(0.5)

def left_turn_90(motors, sec=TURN_SEC_90, speed=SPEED):
    v = sp(speed)
    motors[0].throttle = -v
    motors[1].throttle = -v
    motors[2].throttle =  v
    motors[3].throttle =  v
    time.sleep(sec)
    stop_all(motors)
    time.sleep(0.3)

def right_turn_90(motors, sec=TURN_SEC_90, speed=SPEED):
    v = sp(speed)
    motors[0].throttle =  v
    motors[1].throttle =  v
    motors[2].throttle = -v
    motors[3].throttle = -v
    time.sleep(sec)
    stop_all(motors)
    time.sleep(0.3)

def forward_cells(motors, n=1):
    forward_time(motors, FWD_SEC_1CELL * n, speed=SPEED)

def desired_heading(dx, dy):
    if dx == 1 and dy == 0:  return 0
    if dx == 0 and dy == 1:  return 1
    if dx == -1 and dy == 0: return 2
    if dx == 0 and dy == -1: return 3
    raise ValueError(f"한 번에 1칸 이동만 지원: dx={dx}, dy={dy}")

def rotate_to(target, motors):
    global heading
    diff = (target - heading) % 4
    if diff == 0:
        return
    elif diff == 1:
        left_turn_90(motors)
    elif diff == 3:
        right_turn_90(motors)
    elif diff == 2:
        left_turn_90(motors)
        left_turn_90(motors)
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
# 팔/머리 동작
# =========================================================
def arm_grip_action(arm1, arm2, grip):
    if grip is None:
        print("[WARN] GRIP 서보 없음 - 스킵")
        return
    if arm1 is not None and arm2 is not None:
        arm1.angle = ARM1_HOME
        arm2.angle = ARM2_HOME
        time.sleep(0.2)
        arm1.angle = ARM1_EXTEND
        arm2.angle = ARM2_EXTEND
        time.sleep(0.5)
    grip.angle = GRIP_OPEN
    time.sleep(5)
    grip.angle = GRIP_CLOSE
    time.sleep(0.3)
    if arm1 is not None and arm2 is not None:
        arm1.angle = ARM1_HOME
        arm2.angle = ARM2_HOME
        time.sleep(0.5)

def head_shake_only(head_yaw):
    if head_yaw is None:
        print("[WARN] HEAD_YAW 서보 없음 - 도리도리 스킵")
        return
    head_yaw.angle = HEAD_YAW_CENTER
    time.sleep(0.15)
    for _ in range(2):
        head_yaw.angle = HEAD_YAW_LEFT
        time.sleep(0.25)
        head_yaw.angle = HEAD_YAW_RIGHT
        time.sleep(0.25)
    head_yaw.angle = HEAD_YAW_CENTER
    time.sleep(0.2)

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

    head_yaw = make_servo(pwm, HEAD_YAW_CH)
    arm1 = make_servo(pwm, ARM_J1_CH)
    arm2 = make_servo(pwm, ARM_J2_CH)
    grip = make_servo(pwm, GRIP_CH)

    try:
        stop_all(motors)
        print("[RUN] 6 groups start")

        for idx, pos in enumerate(PATH):
            print(f"\n[GROUP {idx+1}/{len(PATH)}] pos={pos}")

            if idx > 0:
                x0, y0 = PATH[idx-1]
                x1, y1 = pos
                dx, dy = x1 - x0, y1 - y0
                tgt = desired_heading(dx, dy)
                rotate_to(tgt, motors)
                forward_cells(motors, 1)
                stop_all(motors)

            record_wav()
            try:
                text = stt_transcribe(client)
            except Exception as e:
                text = ""
                print(f"[STT ERR] {e}")

            ratio = english_ratio(text)
            en, ko = count_lang(text)

            print(f"[TXT] {text}")
            print(f"[RATIO] en={en}, ko={ko}, english_ratio={ratio:.3f}")

            if ratio >= EN_THRESHOLD:
                print("[DECISION] English >= 0.80 -> 집게 5초 열고 닫기")
                arm_grip_action(arm1, arm2, grip)
            else:
                print("[DECISION] English < 0.80 -> 도리도리")
                head_shake_only(head_yaw)

        print("\n[DONE] mission complete")

    finally:
        stop_all(motors)
        try:
            pwm.deinit()
        except Exception:
            pass

if __name__ == "__main__":
    main()
