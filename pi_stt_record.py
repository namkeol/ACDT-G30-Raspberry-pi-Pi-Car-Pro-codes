import os
from datetime import datetime
import time
import threading

import sounddevice as sd
import soundfile as sf
from openai import OpenAI

# --- OpenAI 클라이언트 ---
client = OpenAI()   # 환경변수에 API KEY 저장했다면 괄호 비워두기


# --- 설정 ---
SAVE_DIR = "/home/pi/recorded_voice"  # 라즈베리파이 저장 경로
DURATION_SEC = 20
SAMPLE_RATE = 16000
CHANNELS = 1


def find_usb_microphone():
    """USB 마이크 자동 탐색"""
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        name = dev["name"].lower()
        if dev["max_input_channels"] > 0:
            if ("usb" in name) or ("microphone" in name) or ("audio" in name):
                print(f"🔍 USB 마이크 자동 감지됨: index={idx}, name={dev['name']}")
                return idx
    raise RuntimeError("❌ USB 마이크를 찾을 수 없습니다. 장치를 연결했는지 확인하세요.")


def countdown_timer(duration_sec: int, stop_event: threading.Event):
    """녹음 중 실시간 카운트업 표시"""
    for sec in range(1, duration_sec + 1):
        if stop_event.is_set():
            break
        print(f"\r⏱️ 녹음 진행 중: {sec:02d} / {duration_sec:02d} 초", end="")
        time.sleep(1)
    print()


def record_audio_to_wav() -> str:
    os.makedirs(SAVE_DIR, exist_ok=True)

    # USB 마이크 자동 검색
    mic_index = find_usb_microphone()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(SAVE_DIR, f"record_{ts}.wav")

    print("\n===================================")
    print("🎤 [상태] 준비 완료! 3초 후 녹음 시작")
    print("===================================\n")
    time.sleep(3)

    print("🎙️ [상태] 녹음 시작!! (장치 index =", mic_index, ")")

    audio = sd.rec(
        int(DURATION_SEC * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        device=mic_index
    )

    stop_event = threading.Event()
    timer_thread = threading.Thread(target=countdown_timer, args=(DURATION_SEC, stop_event))
    timer_thread.start()

    sd.wait()
    stop_event.set()
    timer_thread.join()

    print("\n🛑 [상태] 녹음 종료!")
    print("💾 저장 중...")

    sf.write(out_path, audio, SAMPLE_RATE)
    print(f"✅ 저장 완료: {out_path}")

    return out_path


def transcribe_audio(path: str):
    print("\n🔄 [상태] OpenAI에 음성 → 텍스트 변환 요청 중...")

    with open(path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=f,
            model="gpt-4o-transcribe",
            response_format="json",
        )

    text = getattr(result, "text", "") or str(result)

    print("\n===== 📝 변환된 텍스트 =====")
    print(text)
    print("============================")

    return text


if __name__ == "__main__":
    wav_path = record_audio_to_wav()
    transcribe_audio(wav_path)
