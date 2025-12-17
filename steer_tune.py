import time
from adafruit_motor import motor, servo
from adafruit_pca9685 import PCA9685
import busio
from board import SCL, SDA

# PCA9685 초기화
i2c = busio.I2C(SCL, SDA)
pwm = PCA9685(i2c)
pwm.frequency = 50

# 모터/서보 세팅 (예시 채널)
STEER_CH = 4
M1_IN1, M1_IN2 = 15, 14
M2_IN1, M2_IN2 = 12, 13
M3_IN1, M3_IN2 = 11, 10
M4_IN1, M4_IN2 = 8,  9

steer = servo.Servo(pwm.channels[STEER_CH], min_pulse=500, max_pulse=2500)

from adafruit_motor import motor
m1 = motor.DCMotor(pwm.channels[M1_IN1], pwm.channels[M1_IN2])
m2 = motor.DCMotor(pwm.channels[M2_IN1], pwm.channels[M2_IN2])
m3 = motor.DCMotor(pwm.channels[M3_IN1], pwm.channels[M3_IN2])
m4 = motor.DCMotor(pwm.channels[M4_IN1], pwm.channels[M4_IN2])

motors = [m1, m2, m3, m4]
for m in motors:
    m.decay_mode = motor.SLOW_DECAY

def sp(x):
    return max(0, min(100, x)) / 100.0

def forward_test(sec=1, speed=30):
    v = sp(speed)
    for m in motors:
        m.throttle = v
    time.sleep(sec)
    for m in motors:
        m.throttle = 0

# 자동 테스트 범위 설정
start_angle = 95
end_angle = 115
step = 2

for angle in range(start_angle, end_angle+1, step):
    steer.angle = angle
    print(f"Testing STEER_CENTER = {angle}")
    forward_test(2)
    print("Check the path and adjust angle accordingly")
    time.sleep(2)  # 로봇 이동 후 확인 시간
