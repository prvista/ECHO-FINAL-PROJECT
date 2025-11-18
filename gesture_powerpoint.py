import asyncio
import cv2
import mediapipe as mp
import pyautogui
import psutil
import time
from livekit.agents import AgentSession, Agent, RoomInputOptions

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

def is_powerpoint_open():
    """Check if PowerPoint is running."""
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] and "POWERPNT.EXE" in proc.info["name"].upper():
            return True
    return False


async def gesture_controller():
    """Runs continuously and activates only while PowerPoint is open."""
    hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
    active = False
    cap = None
    last_action_time = 0
    cooldown = 1.5

    print("🖐 Gesture control system ready. Waiting for PowerPoint to open...")

    while True:
        if is_powerpoint_open() and not active:
            # PowerPoint just opened → start camera
            print("📊 PowerPoint detected — starting gesture control.")
            cap = cv2.VideoCapture(0)
            active = True

        elif not is_powerpoint_open() and active:
            # PowerPoint just closed → stop camera
            print("❌ PowerPoint closed — stopping gesture control.")
            active = False
            if cap:
                cap.release()
                cap = None
            cv2.destroyAllWindows()

        if active and cap:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                    index_tip = hand_landmarks.landmark[8]
                    thumb_tip = hand_landmarks.landmark[4]

                    # 👆 Finger up → Next Slide
                    if index_tip.y < hand_landmarks.landmark[6].y:
                        if time.time() - last_action_time > cooldown:
                            pyautogui.press("right")
                            print("➡ Next Slide")
                            last_action_time = time.time()

                    # 🤏 Pinch → Previous Slide
                    dist = abs(index_tip.x - thumb_tip.x)
                    if dist < 0.05:
                        if time.time() - last_action_time > cooldown:
                            pyautogui.press("left")
                            print("⬅ Previous Slide")
                            last_action_time = time.time()

            cv2.imshow("Gesture Controller", frame)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC = manual exit
                print("👋 Gesture control manually stopped.")
                cap.release()
                cv2.destroyAllWindows()
                active = False

        await asyncio.sleep(0.2)  # small delay to avoid CPU overuse