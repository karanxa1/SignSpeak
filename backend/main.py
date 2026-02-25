import os
import time
import cv2
import math
import numpy as np
import threading
import asyncio
import io
import sys
import pkg_resources

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

import mediapipe as mp
import speech_recognition as sr
import symspellpy
from deep_translator import GoogleTranslator, constants
import edge_tts

try:
    import ai_edge_litert.interpreter as tflite
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow as tf
        tflite = tf.lite

# -------------------------
# APPLICATON STATE & ML INIT
# -------------------------

state = {
    "sentence": " ",
    "character": "",
    "confidence": 0.0,
    "suggestions": [" ", " ", " ", " "],
    "is_speaking": False,
    "gesture_control": False,
    "gesture_action": ""
}

# SymSpell Init
sym_spell = symspellpy.SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
dictionary_path = pkg_resources.resource_filename("symspellpy", "frequency_dictionary_en_82_765.txt")
bigram_path = pkg_resources.resource_filename("symspellpy", "frequency_bigramdictionary_en_243_342.txt")
sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1)
sym_spell.load_bigram_dictionary(bigram_path, term_index=0, count_index=2)

# TFLite Init
interpreter = tflite.Interpreter(model_path="model.tflite")
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# Global variables
camera_frame = None
skeleton_frame = None
prev_char = ""
ten_prev_char = [" "] * 10
count = -1
vs = None

app = FastAPI(title="SignSpeak API")

# Setup CORS for Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def distance(p1, p2):
    return math.sqrt(((p1[0] - p2[0]) ** 2) + ((p1[1] - p2[1]) ** 2))

def detect_ASL_number(pts):
    """Detect ASL digits 0-9 from hand landmarks. Returns digit str or None."""
    thumb_up = pts[4][1] < pts[3][1]
    index_up = pts[8][1] < pts[6][1]
    middle_up = pts[12][1] < pts[10][1]
    ring_up = pts[16][1] < pts[14][1]
    pinky_up = pts[20][1] < pts[18][1]
    thumb_touch = lambda tip_idx: distance(pts[4], pts[tip_idx]) < 35
    # 0: closed fist
    if not thumb_up and not index_up and not middle_up and not ring_up and not pinky_up:
        return "0"
    # 1: only index
    if index_up and not middle_up and not ring_up and not pinky_up:
        return "1"
    # 2: index + middle
    if index_up and middle_up and not ring_up and not pinky_up:
        return "2"
    # 3: index + middle + ring
    if index_up and middle_up and ring_up and not pinky_up:
        return "3"
    # 4: four fingers up, thumb in
    if index_up and middle_up and ring_up and pinky_up and not thumb_up:
        return "4"
    # 5: open palm
    if thumb_up and index_up and middle_up and ring_up and pinky_up:
        return "5"
    # 6-9: thumb touches finger (palm out)
    if not index_up and not middle_up and not ring_up and not pinky_up:
        if thumb_touch(20): return "6"
        if thumb_touch(16): return "7"
        if thumb_touch(12): return "8"
        if thumb_touch(8): return "9"
    return None

def predict_character(white_img, pts):
    white = white_img.astype(np.float32)
    white = white.reshape(1, 400, 400, 3)
    
    interpreter.set_tensor(input_details[0]['index'], white)
    interpreter.invoke()
    raw_prob = interpreter.get_tensor(output_details[0]['index'])[0].copy()
    max_confidence = float(np.max(raw_prob))
    prob = raw_prob
    
    ch1 = int(np.argmax(prob))
    prob[ch1] = 0
    ch2 = int(np.argmax(prob))
    
    pl = [ch1, ch2]
    
    l_aemnst = [[5, 2], [5, 3], [3, 5], [3, 6], [3, 0], [3, 2], [6, 4], [6, 1], [6, 2], [6, 6], [6, 7], [6, 0], [6, 5], [4, 1], [1, 0], [1, 1], [6, 3], [1, 6], [5, 6], [5, 1], [4, 5], [1, 4], [1, 5], [2, 0], [2, 6], [4, 6], [1, 0], [5, 7], [1, 6], [6, 1], [7, 6], [2, 5], [7, 1], [5, 4], [7, 0], [7, 5], [7, 2]]
    if pl in l_aemnst:
        if (pts[6][1]<pts[8][1] and pts[10][1]<pts[12][1] and pts[14][1]<pts[16][1] and pts[18][1]<pts[20][1]):
            ch1 = 0
            
    if pl in [[2, 2], [2, 1]]:
        if (pts[5][0] < pts[4][0]): ch1 = 0
            
    if ch1 == 0:
        ch1 = 'S'
        if pts[4][0] < pts[6][0] and pts[4][0] < pts[10][0] and pts[4][0] < pts[14][0] and pts[4][0] < pts[18][0]: ch1 = 'A'
        if pts[4][0] > pts[6][0] and pts[4][0] < pts[10][0] and pts[4][0] < pts[14][0] and pts[4][0] < pts[18][0] and pts[4][1] < pts[14][1] and pts[4][1] < pts[18][1]: ch1 = 'T'
        if pts[4][1] > pts[8][1] and pts[4][1] > pts[12][1] and pts[4][1] > pts[16][1] and pts[4][1] > pts[20][1]: ch1 = 'E'
        if pts[4][0] > pts[6][0] and pts[4][0] > pts[10][0] and pts[4][0] > pts[14][0] and pts[4][1] < pts[18][1]: ch1 = 'M'
        if pts[4][0] > pts[6][0] and pts[4][0] > pts[10][0] and pts[4][1] < pts[18][1] and pts[4][1] < pts[14][1]: ch1 = 'N'
    elif ch1 == 2:
        ch1 = 'C' if distance(pts[12], pts[4]) > 42 else 'O'
    elif ch1 == 3:
        ch1 = 'G' if distance(pts[8], pts[12]) > 72 else 'H'
    elif ch1 == 7:
        ch1 = 'Y' if distance(pts[8], pts[4]) > 42 else 'J'
    elif ch1 == 4:
        ch1 = 'L'
    elif ch1 == 6:
        ch1 = 'X'
    elif ch1 == 5:
        if pts[4][0] > pts[12][0] and pts[4][0] > pts[16][0] and pts[4][0] > pts[20][0]:
            ch1 = 'Z' if pts[8][1] < pts[5][1] else 'Q'
        else:
            ch1 = 'P'
    elif ch1 == 1:
        if pts[6][1]>pts[8][1] and pts[10][1]>pts[12][1] and pts[14][1]>pts[16][1] and pts[18][1]>pts[20][1]: ch1 = 'B'
        elif pts[6][1]>pts[8][1] and pts[10][1]<pts[12][1] and pts[14][1]<pts[16][1] and pts[18][1]<pts[20][1]: ch1 = 'D'
        elif pts[6][1]<pts[8][1] and pts[10][1]>pts[12][1] and pts[14][1]>pts[16][1] and pts[18][1]>pts[20][1]: ch1 = 'F'
        elif pts[6][1]<pts[8][1] and pts[10][1]<pts[12][1] and pts[14][1]<pts[16][1] and pts[18][1]>pts[20][1]: ch1 = 'I'
        elif pts[6][1]>pts[8][1] and pts[10][1]>pts[12][1] and pts[14][1]>pts[16][1] and pts[18][1]<pts[20][1]: ch1 = 'W'
    
    ch1 = str(ch1)
    
    if ch1 in ['1', 'E', 'S', 'X', 'Y', 'B']:
        if pts[6][1]>pts[8][1] and pts[10][1]<pts[12][1] and pts[14][1]<pts[16][1] and pts[18][1]>pts[20][1]:
            ch1 = " "
            
    if ch1 in ['E', 'Y', 'B']:
        if pts[4][0]<pts[5][0] and pts[6][1]>pts[8][1] and pts[10][1]>pts[12][1] and pts[14][1]>pts[16][1] and pts[18][1]>pts[20][1]:
            ch1 = "next"
            
    if ch1 in ['next', 'B', 'C', 'H', 'F', 'X', 'Next']:
         if pts[0][0]>pts[8][0] and pts[0][0]>pts[12][0] and pts[0][0]>pts[16][0] and pts[0][0]>pts[20][0] and pts[4][1]<pts[8][1] and pts[4][1]<pts[12][1] and pts[4][1]<pts[16][1] and pts[4][1]<pts[20][1] and pts[4][1]<pts[6][1] and pts[4][1]<pts[10][1] and pts[4][1]<pts[14][1] and pts[4][1]<pts[18][1]:
             ch1 = "Backspace"

    return ch1, max_confidence

def detect_gesture(pts):
    """Detect UI-control gestures from landmark points."""
    # Finger up checks (tip above pip)
    thumb_up = pts[4][1] < pts[3][1]
    index_up = pts[8][1] < pts[6][1]
    middle_up = pts[12][1] < pts[10][1]
    ring_up = pts[16][1] < pts[14][1]
    pinky_up = pts[20][1] < pts[18][1]
    
    # Thumbs Up: only thumb extended
    if thumb_up and not index_up and not middle_up and not ring_up and not pinky_up:
        return "translate"
    # Open Palm: all five fingers up
    if thumb_up and index_up and middle_up and ring_up and pinky_up:
        return "clear"
    # Peace Sign: index + middle up, rest down
    if index_up and middle_up and not ring_up and not pinky_up:
        return "speak"
    return ""

def process_state(ch1, confidence):
    global count, prev_char
    
    state["confidence"] = round(confidence * 100, 1)
    
    # Gesture control mode
    if state["gesture_control"]:
        state["character"] = ch1
        return
    
    if ch1 == "next" and prev_char != "next":
        if ten_prev_char[(count-2)%10] != "next":
            if ten_prev_char[(count-2)%10] == "Backspace":
                state["sentence"] = state["sentence"][:-1]
            else:
                state["sentence"] += ten_prev_char[(count-2)%10]
    
    elif ch1 == "  " and prev_char != "  ":
         state["sentence"] += "  "

    prev_char = ch1
    state["character"] = ch1
    count += 1
    ten_prev_char[count%10] = ch1
    
    # Run SymSpell
    words = state["sentence"].strip().split(" ")
    if len(words) > 0:
        last_word = words[-1]
        if len(last_word.strip()) > 0:
            suggs = sym_spell.lookup(last_word, symspellpy.Verbosity.CLOSEST, max_edit_distance=2)[:4]
            state["suggestions"] = [s.term for s in suggs] + [" "] * (4 - len(suggs))

def background_camera_loop():
    global camera_frame, vs, skeleton_frame
    vs = cv2.VideoCapture(0)
    
    connections = [
        (0,1), (1,2), (2,3), (3,4),
        (5,6), (6,7), (7,8),
        (9,10), (10,11), (11,12),
        (13,14), (14,15), (15,16),
        (17,18), (18,19), (19,20),
        (5,9), (9,13), (13,17), (0,5), (0,17)
    ]
    
    while True:
        ok, frame = vs.read()
        if not ok:
            time.sleep(0.1)
            continue
            
        frame = cv2.flip(frame, 1)
        _, buffer_cam = cv2.imencode('.jpg', frame)
        camera_frame = buffer_cam.tobytes()

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)
        
        h, w, c = frame.shape
        display_white = np.ones((h, w, 3), dtype=np.uint8) * 255
        
        if results.multi_hand_landmarks:
            landmarks = results.multi_hand_landmarks[0]
            abs_pts = [[int(lm.x * w), int(lm.y * h)] for lm in landmarks.landmark]
            
            # Draw on full-size display canvas
            for (i, j) in connections:
                cv2.line(display_white, tuple(abs_pts[i]), tuple(abs_pts[j]), (0, 0, 0), 2)
            for i in range(21):
                cv2.circle(display_white, tuple(abs_pts[i]), 3, (0, 0, 255), -1)
            
            # Prepare 400x400 cropped canvas for TFLite Inference
            min_x = min([p[0] for p in abs_pts])
            min_y = min([p[1] for p in abs_pts])
            max_x = max([p[0] for p in abs_pts])
            max_y = max([p[1] for p in abs_pts])
            
            bw = max_x - min_x
            bh = max_y - min_y
            
            rel_pts = [[p[0] - min_x, p[1] - min_y] for p in abs_pts]
            os_x = max(0, ((400 - bw) // 2) - 15)
            os_y = max(0, ((400 - bh) // 2) - 15)
            pts = [[p[0] + os_x, p[1] + os_y] for p in rel_pts]
            
            inference_white = np.ones((400, 400, 3), dtype=np.uint8) * 255
            for (i, j) in connections:
                cv2.line(inference_white, tuple(pts[i]), tuple(pts[j]), (0, 255, 0), 3)
            for i in range(21):
                cv2.circle(inference_white, tuple(pts[i]), 2, (0, 0, 255), 1)

            ch1, conf = predict_character(inference_white, pts)
            num = detect_ASL_number(abs_pts) if not state["gesture_control"] else None
            if num is not None:
                ch1, conf = num, 0.85

            if state["gesture_control"]:
                gesture = detect_gesture(abs_pts)
                state["gesture_action"] = gesture
                state["character"] = gesture if gesture else ch1
                state["confidence"] = round(conf * 100, 1)
            else:
                state["gesture_action"] = ""
                process_state(ch1, conf)
            
        _, buffer_skel = cv2.imencode('.jpg', display_white)
        skeleton_frame = buffer_skel.tobytes()
        
        # Yield to asyncio event loop to prevent starvation
        time.sleep(0.01)

# Spin up background loop
threading.Thread(target=background_camera_loop, daemon=True).start()

# -------------------------
# FASTAPI ROUTES
# -------------------------

def generate_feed(src="camera"):
    while True:
        frame = camera_frame if src == "camera" else skeleton_frame
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03) # roughly 30 FPS throttle


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_feed("camera"), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/skeleton_feed")
def skeleton_feed():
    return StreamingResponse(generate_feed("skeleton"), media_type="multipart/x-mixed-replace; boundary=frame")

active_connections = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await asyncio.sleep(0.1)
            await websocket.send_json(state)
    except WebSocketDisconnect:
        active_connections.remove(websocket)


class SuggestionRequest(BaseModel):
    word: str

@app.post("/apply_suggestion")
def apply_suggestion(req: SuggestionRequest):
    parts = state["sentence"].strip().split(" ")
    if len(parts) > 0:
        parts[-1] = req.word.upper()
    state["sentence"] = " ".join(parts) + " "
    return {"success": True}

@app.post("/clear")
def clear():
    state["sentence"] = " "
    state["suggestions"] = [" ", " ", " ", " "]
    return {"success": True}

class AppendTextRequest(BaseModel):
    text: str

@app.post("/append_text")
def append_text(req: AppendTextRequest):
    t = req.text.strip()
    if t:
        state["sentence"] = (state["sentence"].rstrip() + " " + t + " ").lstrip()
        words = state["sentence"].strip().split(" ")
        if words:
            last = words[-1]
            if last:
                suggs = sym_spell.lookup(last, symspellpy.Verbosity.CLOSEST, max_edit_distance=2)[:4]
                state["suggestions"] = [s.term for s in suggs] + [" "] * (4 - len(suggs))
    return {"success": True}

@app.post("/toggle_gesture")
def toggle_gesture():
    state["gesture_control"] = not state["gesture_control"]
    state["gesture_action"] = ""
    return {"gesture_control": state["gesture_control"]}

class TranslateRequest(BaseModel):
    text: str
    src: str = "english"
    dest: str = "hindi"

@app.post("/translate")
def translate(req: TranslateRequest):
    t = GoogleTranslator(source=req.src, target=req.dest)
    try:
        translated = t.translate(req.text)
        return {"translated": translated}
    except Exception as e:
        return {"error": str(e)}

class SpeakRequest(BaseModel):
    text: str
    gender: str = "Male"
    speed: float = 1.0
from langdetect import detect
from gtts import gTTS
import pygame

pygame.mixer.init()

@app.post("/speak")
async def speak(req: SpeakRequest):
    clean = req.text.strip()
    if state["is_speaking"] or len(clean) < 2:
        return {"success": False, "reason": "Text too short or already speaking"}
    state["is_speaking"] = True
    
    async def _speak():
        try:
            try:
                lang = detect(clean)
            except:
                lang = "en"
                
            if lang == "hi":
                # Fallback to gtts for Hindi because edge-tts is unstable with Indic scripts on Mac
                tts = gTTS(text=clean, lang='hi')
                tts.save("temp.mp3")
                pygame.mixer.music.load("temp.mp3")
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)
                pygame.mixer.music.unload()
            else:
                voice = 'en-US-ChristopherNeural' if req.gender == "Male" else 'en-US-JennyNeural'
                rate = f"+{int((req.speed - 1.0) * 100)}%" if req.speed > 1 else "+0%"
                communicate = edge_tts.Communicate(clean, voice, rate=rate)
                await communicate.save("temp.mp3")
                
                if sys.platform == "darwin": os.system("afplay temp.mp3")
                elif sys.platform == "win32": os.system("start temp.mp3")
                else: os.system("mpg123 temp.mp3")
        except Exception as e:
            print(f"[TTS Error] {e}")
        finally:
            state["is_speaking"] = False
            if os.path.exists("temp.mp3"):
                try:
                    os.remove("temp.mp3")
                except:
                    pass

    asyncio.create_task(_speak())
    return {"success": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
