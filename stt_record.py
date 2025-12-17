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
SAVE_DIR = r"C:\Users\이남걸(학교)\Desktop\recorded_voice"
DURATION_SEC = 20
SAMPLE_RATE = 16000
CHANNELS = 1

# USB 마이크 번호
USB_MIC_INDEX = 1    # "1 마이크(USB PnP Sound Device)"


def countdown_timer(duration_sec: int, stop_event: threading.Event):
    """녹음 중 실시간 카운트업 표시"""
    for sec in range(1, duration_sec + 1):
        if stop_event.is_set():
            break
        print(f"\r⏱️ 녹음 진행 중: {sec:02d} / {duration_sec:02d} 초", end="")
        time.sleep(1)
    print()  # 줄바꿈


def record_audio_to_wav() -> str:
    os.makedirs(SAVE_DIR, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(SAVE_DIR, f"record_{ts}.wav")

    print("\n===================================")
    print("🎤 [상태] 준비 완료! 3초 후 녹음 시작")
    print("===================================\n")
    time.sleep(3)

    print("🎙️ [상태] 녹음 시작!!")

    # 녹음 시작
    audio = sd.rec(
        int(DURATION_SEC * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        device=USB_MIC_INDEX
    )

    # 카운터 스레드 시작
    stop_event = threading.Event()
    timer_thread = threading.Thread(target=countdown_timer, args=(DURATION_SEC, stop_event))
    timer_thread.start()

    # 녹음 종료까지 대기
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
