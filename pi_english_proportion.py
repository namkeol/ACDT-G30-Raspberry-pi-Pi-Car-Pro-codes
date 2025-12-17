import os
from datetime import datetime
import time
import threading
import re

import sounddevice as sd
import soundfile as sf
from openai import OpenAI

# --- OpenAI 클라이언트 ---
client = OpenAI()   # 환경변수에 API KEY 저장했다면 괄호 비워두기

# --- 설정 ---
SAVE_DIR = "/home/pi/recorded_voice"  # 라즈베리파이 저장 경로
DURATION_SEC = 20
SAMPLE_RATE = 44100  # USB 마이크 안전 샘플레이트
CHANNELS = 1

# USB 마이크 장치 고정
MIC_INDEX = 0  # 'USB PnP Sound Device'

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

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(SAVE_DIR, f"record_{ts}.wav")

    print("\n===================================")
    print("🎤 [상태] 준비 완료! 3초 후 녹음 시작")
    print("===================================\n")
    time.sleep(3)

    print(f"🎙️ [상태] 녹음 시작!! (장치: {MIC_INDEX}, 샘플레이트: {SAMPLE_RATE})")

    audio = sd.rec(
        int(DURATION_SEC * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        device=MIC_INDEX
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

def analyze_english_ratio(text: str):
    """STT 텍스트 속 영어 단어 비율 계산"""
    english_words = re.findall(r"[A-Za-z]+", text)
    all_words = re.findall(r"[A-Za-z0-9가-힣]+", text)

    eng_count = len(english_words)
    total_count = len(all_words)

    ratio = (eng_count / total_count * 100) if total_count > 0 else 0

    print("\n===== 🔍 영어 단어 비율 분석 =====")
    print(f"영어 단어 수: {eng_count}")
    print(f"전체 단어 수: {total_count}")
    print(f"영어 비율: {ratio:.2f}%")
    print(f"영어 단어 리스트: {english_words}")
    print("================================")

    return ratio

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

    # 영어 비율 분석 추가
    analyze_english_ratio(text)

    return text

if __name__ == "__main__":
    wav_path = record_audio_to_wav()
    transcribe_audio(wav_path)
