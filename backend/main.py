import os
import time
import cv2
import math
import numpy as np
import threading
import asyncio
import sys
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

import mediapipe as mp
import symspellpy
from deep_translator import GoogleTranslator
import edge_tts

try:
    import ai_edge_litert.interpreter as tflite
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        try:
            import tensorflow as tf
            tflite = tf.lite
        except ImportError:
            tflite = None

# -------------------------
# CONSTANTS  (built once, reused every frame)
# -------------------------

VALID_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

# Pairs that trigger the landmark-based AEMNST override
L_AEMNST = frozenset(
    map(tuple, [[5,2],[5,3],[3,5],[3,6],[3,0],[3,2],[6,4],[6,1],[6,2],
                [6,6],[6,7],[6,0],[6,5],[4,1],[1,0],[1,1],[6,3],[1,6],
                [5,6],[5,1],[4,5],[1,4],[1,5],[2,0],[2,6],[4,6],[1,0],
                [5,7],[1,6],[6,1],[7,6],[2,5],[7,1],[5,4],[7,0],[7,5],[7,2]])
)

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (5,6),(6,7),(7,8),
    (9,10),(10,11),(11,12),
    (13,14),(14,15),(15,16),
    (17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),(0,5),(0,17)
]

# JPEG encode params — quality 75 cuts bandwidth ~40% vs default 95 with no visible lag
JPEG_PARAMS = [cv2.IMWRITE_JPEG_QUALITY, 75]

# MediaPipe processes frames at this resolution (saves ~60% CPU vs 640×480)
MP_WIDTH  = 320
MP_HEIGHT = 240

# TFLite inference canvas size (must match training)
INFER_SIZE = 400

# How many camera frames to skip between ML inferences (0 = every frame)
# On a slow Windows laptop set to 1 (infer every 2nd frame) for ~2× CPU relief
INFER_SKIP = 1

# -------------------------
# ML INIT
# -------------------------

interpreter = None
input_details = output_details = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.tflite")

if tflite and os.path.exists(MODEL_PATH):
    interpreter = tflite.Interpreter(model_path=MODEL_PATH, num_threads=2)
    interpreter.allocate_tensors()
    input_details  = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
else:
    if not os.path.exists(MODEL_PATH):
        print("[SignSpeak] model.tflite not found — sign detection disabled.")
    else:
        print("[SignSpeak] TFLite not available — sign detection disabled.")

# -------------------------
# APPLICATION STATE
# -------------------------

state = {
    "sentence":        " ",
    "character":       "",
    "confidence":      0.0,
    "suggestions":     [" ", " ", " ", " "],
    "is_speaking":     False,
    "gesture_control": False,
    "gesture_action":  ""
}

# -------------------------
# SYMSPELL INIT
# -------------------------

sym_spell = symspellpy.SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
_sym_dir  = os.path.dirname(symspellpy.__file__)
sym_spell.load_dictionary(
    os.path.join(_sym_dir, "frequency_dictionary_en_82_765.txt"),
    term_index=0, count_index=1
)
sym_spell.load_bigram_dictionary(
    os.path.join(_sym_dir, "frequency_bigramdictionary_en_243_342.txt"),
    term_index=0, count_index=2
)

# -------------------------
# MEDIAPIPE INIT
# -------------------------

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6,
    model_complexity=0           # lightest model — big win on CPU-only laptops
)

# -------------------------
# GLOBAL FRAME BUFFERS
# (bytes written by camera thread, read by MJPEG generators)
# -------------------------

camera_frame   = None
skeleton_frame = None

# Pre-allocated numpy canvases (avoids malloc every frame)
_display_white  = None   # full-res white canvas for skeleton display
_infer_white    = np.ones((INFER_SIZE, INFER_SIZE, 3), dtype=np.uint8) * 255
_infer_input    = np.ones((1, INFER_SIZE, INFER_SIZE, 3), dtype=np.float32)

# Auto-type state
prev_char        = ""
count            = -1
ten_prev_char    = [" "] * 10
auto_type_char   = ""
auto_type_cooldown = 0.0
vs               = None

# State change tracking for smart WebSocket push
_last_sent_state: dict = {}

# -------------------------
# FASTAPI APP
# -------------------------

app = FastAPI(title="SignSpeak API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# HELPER FUNCTIONS
# -------------------------

def distance(p1, p2):
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return math.sqrt(dx*dx + dy*dy)


def detect_ASL_number(pts):
    """Detect ASL digits 0-9 from hand landmarks. Returns digit str or None."""
    thumb_up  = pts[4][1]  < pts[3][1]
    index_up  = pts[8][1]  < pts[6][1]
    middle_up = pts[12][1] < pts[10][1]
    ring_up   = pts[16][1] < pts[14][1]
    pinky_up  = pts[20][1] < pts[18][1]

    def thumb_touch(tip_idx):
        return distance(pts[4], pts[tip_idx]) < 35

    if not thumb_up and not index_up and not middle_up and not ring_up and not pinky_up:
        return "0"
    if index_up and not middle_up and not ring_up and not pinky_up:
        return "1"
    if index_up and middle_up and not ring_up and not pinky_up:
        return "2"
    if index_up and middle_up and ring_up and not pinky_up:
        return "3"
    if index_up and middle_up and ring_up and pinky_up and not thumb_up:
        return "4"
    if thumb_up and index_up and middle_up and ring_up and pinky_up:
        return "5"
    if not index_up and not middle_up and not ring_up and not pinky_up:
        if thumb_touch(20): return "6"
        if thumb_touch(16): return "7"
        if thumb_touch(12): return "8"
        if thumb_touch(8):  return "9"
    return None


def predict_character(pts):
    """
    Run TFLite inference using the pre-allocated _infer_white canvas and
    _infer_input tensor buffer — no per-frame allocation.
    pts are already scaled for the 400×400 canvas.
    """
    if interpreter is None:
        return "", 0.0

    # Reuse pre-allocated canvases
    _infer_white[:] = 255
    for (i, j) in HAND_CONNECTIONS:
        cv2.line(_infer_white, tuple(pts[i]), tuple(pts[j]), (0, 255, 0), 3)
    for i in range(21):
        cv2.circle(_infer_white, tuple(pts[i]), 2, (0, 0, 255), 1)

    # Fill pre-allocated float32 input buffer in-place
    np.copyto(_infer_input[0], _infer_white.astype(np.float32))

    interpreter.set_tensor(input_details[0]['index'], _infer_input)
    interpreter.invoke()
    raw_prob = interpreter.get_tensor(output_details[0]['index'])[0].copy()

    max_confidence = float(np.max(raw_prob))
    prob = raw_prob.copy()
    ch1 = int(np.argmax(prob))
    prob[ch1] = 0
    ch2 = int(np.argmax(prob))
    pl = (ch1, ch2)

    # AEMNST disambiguation
    if pl in L_AEMNST:
        if (pts[6][1]<pts[8][1] and pts[10][1]<pts[12][1] and
                pts[14][1]<pts[16][1] and pts[18][1]<pts[20][1]):
            ch1 = 0

    if pl in {(2,2),(2,1)}:
        if pts[5][0] < pts[4][0]:
            ch1 = 0

    if ch1 == 0:
        ch1 = 'S'
        if pts[4][0]<pts[6][0] and pts[4][0]<pts[10][0] and pts[4][0]<pts[14][0] and pts[4][0]<pts[18][0]:
            ch1 = 'A'
        if (pts[4][0]>pts[6][0] and pts[4][0]<pts[10][0] and pts[4][0]<pts[14][0] and
                pts[4][0]<pts[18][0] and pts[4][1]<pts[14][1] and pts[4][1]<pts[18][1]):
            ch1 = 'T'
        if pts[4][1]>pts[8][1] and pts[4][1]>pts[12][1] and pts[4][1]>pts[16][1] and pts[4][1]>pts[20][1]:
            ch1 = 'E'
        if pts[4][0]>pts[6][0] and pts[4][0]>pts[10][0] and pts[4][0]>pts[14][0] and pts[4][1]<pts[18][1]:
            ch1 = 'M'
        if pts[4][0]>pts[6][0] and pts[4][0]>pts[10][0] and pts[4][1]<pts[18][1] and pts[4][1]<pts[14][1]:
            ch1 = 'N'
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
        if pts[4][0]>pts[12][0] and pts[4][0]>pts[16][0] and pts[4][0]>pts[20][0]:
            ch1 = 'Z' if pts[8][1] < pts[5][1] else 'Q'
        else:
            ch1 = 'P'
    elif ch1 == 1:
        if   pts[6][1]>pts[8][1]  and pts[10][1]>pts[12][1]  and pts[14][1]>pts[16][1]  and pts[18][1]>pts[20][1]:  ch1 = 'B'
        elif pts[6][1]>pts[8][1]  and pts[10][1]<pts[12][1]  and pts[14][1]<pts[16][1]  and pts[18][1]<pts[20][1]:  ch1 = 'D'
        elif pts[6][1]<pts[8][1]  and pts[10][1]>pts[12][1]  and pts[14][1]>pts[16][1]  and pts[18][1]>pts[20][1]:  ch1 = 'F'
        elif pts[6][1]<pts[8][1]  and pts[10][1]<pts[12][1]  and pts[14][1]<pts[16][1]  and pts[18][1]>pts[20][1]:  ch1 = 'I'
        elif pts[6][1]>pts[8][1]  and pts[10][1]>pts[12][1]  and pts[14][1]>pts[16][1]  and pts[18][1]<pts[20][1]:  ch1 = 'W'

    ch1 = str(ch1)

    if ch1 in {'1','E','S','X','Y','B'}:
        if pts[6][1]>pts[8][1] and pts[10][1]<pts[12][1] and pts[14][1]<pts[16][1] and pts[18][1]>pts[20][1]:
            ch1 = " "

    if ch1 in {'E','Y','B'}:
        if (pts[4][0]<pts[5][0] and pts[6][1]>pts[8][1] and pts[10][1]>pts[12][1] and
                pts[14][1]>pts[16][1] and pts[18][1]>pts[20][1]):
            ch1 = "next"

    if ch1 in {'next','B','C','H','F','X','Next'}:
        if (pts[0][0]>pts[8][0]  and pts[0][0]>pts[12][0] and pts[0][0]>pts[16][0] and
                pts[0][0]>pts[20][0] and pts[4][1]<pts[8][1]  and pts[4][1]<pts[12][1] and
                pts[4][1]<pts[16][1] and pts[4][1]<pts[20][1] and pts[4][1]<pts[6][1]  and
                pts[4][1]<pts[10][1] and pts[4][1]<pts[14][1] and pts[4][1]<pts[18][1]):
            ch1 = "Backspace"

    return ch1, max_confidence


def detect_gesture(pts):
    """Detect UI-control gestures from landmark points."""
    thumb_up  = pts[4][1]  < pts[3][1]
    index_up  = pts[8][1]  < pts[6][1]
    middle_up = pts[12][1] < pts[10][1]
    ring_up   = pts[16][1] < pts[14][1]
    pinky_up  = pts[20][1] < pts[18][1]

    if thumb_up and not index_up and not middle_up and not ring_up and not pinky_up:
        return "translate"
    if thumb_up and index_up and middle_up and ring_up and pinky_up:
        return "clear"
    if index_up and middle_up and not ring_up and not pinky_up:
        return "speak"
    return ""


def _update_suggestions(word: str):
    """Recompute SymSpell suggestions for the current partial word."""
    if word.strip():
        suggs = sym_spell.lookup(word, symspellpy.Verbosity.CLOSEST, max_edit_distance=2)[:4]
        state["suggestions"] = [s.term for s in suggs] + [" "] * (4 - len(suggs))
    else:
        state["suggestions"] = [" ", " ", " ", " "]


def process_state(ch1, confidence):
    global count, prev_char, auto_type_char, auto_type_cooldown

    state["confidence"] = round(confidence * 100, 1)

    if state["gesture_control"]:
        state["character"] = ch1
        return

    now = time.time()

    if ch1 in VALID_CHARS:
        if ch1 != auto_type_char:
            state["sentence"]  += ch1
            auto_type_char      = ch1
            auto_type_cooldown  = now
        elif (now - auto_type_cooldown) >= 0.4:
            state["sentence"]  += ch1
            auto_type_cooldown  = now
    elif ch1 == " ":
        if auto_type_char != " ":
            words = state["sentence"].strip().split(" ")
            if words and len(words[-1]) > 1:
                suggs = sym_spell.lookup(words[-1], symspellpy.Verbosity.CLOSEST, max_edit_distance=2)
                if suggs:
                    words[-1] = suggs[0].term.upper()
                    state["sentence"] = " ".join(words)
            state["sentence"]  += " "
            auto_type_char      = " "
            auto_type_cooldown  = now
    elif ch1 == "Backspace" and prev_char != "Backspace":
        state["sentence"] = state["sentence"][:-1]
        auto_type_char = ""
    else:
        auto_type_char     = ch1
        auto_type_cooldown = now

    prev_char = ch1
    state["character"] = ch1
    count += 1
    ten_prev_char[count % 10] = ch1

    words = state["sentence"].strip().split(" ")
    if words:
        _update_suggestions(words[-1])


# -------------------------
# BACKGROUND CAMERA LOOP
# -------------------------

def _open_camera():
    """Open camera with the fastest available backend for the platform."""
    if sys.platform == "win32":
        # DSHOW avoids the slow Media Foundation initialisation on Windows
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(0)

    # Request a compact resolution from the driver — less data to move through USB
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    # Minimise internal buffer so we always get the *latest* frame
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def background_camera_loop():
    global camera_frame, skeleton_frame, _display_white

    vs = _open_camera()
    frame_index = 0

    # Cache last good character so we can still update display on skipped frames
    cached_ch1   = ""
    cached_conf  = 0.0

    while True:
        ok, frame = vs.read()
        if not ok:
            time.sleep(0.05)
            continue

        frame = cv2.flip(frame, 1)
        h, w  = frame.shape[:2]

        # --- Camera JPEG (full-res, viewers get the real image) ---
        _, buf = cv2.imencode('.jpg', frame, JPEG_PARAMS)
        camera_frame = buf.tobytes()

        # --- Allocate / reuse display canvas at native resolution ---
        if _display_white is None or _display_white.shape[:2] != (h, w):
            _display_white = np.ones((h, w, 3), dtype=np.uint8) * 255
        else:
            _display_white[:] = 255      # fast in-place reset

        # --- Downscale for MediaPipe (big CPU saving) ---
        small = cv2.resize(frame, (MP_WIDTH, MP_HEIGHT), interpolation=cv2.INTER_LINEAR)
        rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        if results.multi_hand_landmarks:
            landmarks = results.multi_hand_landmarks[0]

            # Scale landmarks back to full-res coordinates
            sx = w / MP_WIDTH
            sy = h / MP_HEIGHT
            abs_pts = [
                [int(lm.x * MP_WIDTH  * sx),
                 int(lm.y * MP_HEIGHT * sy)]
                for lm in landmarks.landmark
            ]

            # Draw skeleton on display canvas
            for (i, j) in HAND_CONNECTIONS:
                cv2.line(_display_white, tuple(abs_pts[i]), tuple(abs_pts[j]), (0, 0, 0), 2)
            for i in range(21):
                cv2.circle(_display_white, tuple(abs_pts[i]), 3, (0, 0, 255), -1)

            # --- ML inference (run every INFER_SKIP+1 frames) ---
            do_infer = (frame_index % (INFER_SKIP + 1) == 0)

            if do_infer:
                # Build 400×400 normalised pts for TFLite
                xs = [p[0] for p in abs_pts]
                ys = [p[1] for p in abs_pts]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                bw = max_x - min_x
                bh = max_y - min_y
                os_x = max(0, ((INFER_SIZE - bw) // 2) - 15)
                os_y = max(0, ((INFER_SIZE - bh) // 2) - 15)
                pts = [[p[0] - min_x + os_x, p[1] - min_y + os_y] for p in abs_pts]

                # Clamp to canvas bounds
                for p in pts:
                    p[0] = max(0, min(INFER_SIZE - 1, p[0]))
                    p[1] = max(0, min(INFER_SIZE - 1, p[1]))

                ch1, conf = predict_character(pts)

                if not state["gesture_control"]:
                    num = detect_ASL_number(abs_pts)
                    if num is not None:
                        ch1, conf = num, 0.85

                cached_ch1  = ch1
                cached_conf = conf

            # Apply state update using cached result
            if state["gesture_control"]:
                gesture = detect_gesture(abs_pts)
                state["gesture_action"] = gesture
                state["character"]      = gesture if gesture else cached_ch1
                state["confidence"]     = round(cached_conf * 100, 1)
            else:
                state["gesture_action"] = ""
                process_state(cached_ch1, cached_conf)

        # --- Skeleton JPEG ---
        _, buf_skel = cv2.imencode('.jpg', _display_white, JPEG_PARAMS)
        skeleton_frame = buf_skel.tobytes()

        frame_index += 1
        # 1 ms sleep — yields the GIL without introducing perceptible lag
        time.sleep(0.001)


threading.Thread(target=background_camera_loop, daemon=True).start()

# -------------------------
# MJPEG FEED GENERATORS
# -------------------------

def generate_feed(src="camera"):
    """Yield MJPEG frames only when the buffer has actually changed."""
    last = None
    while True:
        frame = camera_frame if src == "camera" else skeleton_frame
        if frame and frame is not last:
            last = frame
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.033)   # cap at ~30 fps on the sender side


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_feed("camera"),
                             media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/skeleton_feed")
def skeleton_feed():
    return StreamingResponse(generate_feed("skeleton"),
                             media_type="multipart/x-mixed-replace; boundary=frame")

# -------------------------
# WEBSOCKET  (push only on change)
# -------------------------

active_connections: list[WebSocket] = []

def _state_snapshot():
    """Return a lightweight copy of the fields the frontend cares about."""
    return {
        "sentence":        state["sentence"],
        "character":       state["character"],
        "confidence":      state["confidence"],
        "suggestions":     list(state["suggestions"]),
        "is_speaking":     state["is_speaking"],
        "gesture_control": state["gesture_control"],
        "gesture_action":  state["gesture_action"],
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    last_snap: dict = {}
    try:
        while True:
            await asyncio.sleep(0.05)   # check at 20 Hz
            snap = _state_snapshot()
            if snap != last_snap:       # only send when something changed
                await websocket.send_json(snap)
                last_snap = snap
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)

# -------------------------
# REST ENDPOINTS
# -------------------------

class SuggestionRequest(BaseModel):
    word: str

@app.post("/apply_suggestion")
def apply_suggestion(req: SuggestionRequest):
    parts = state["sentence"].strip().split(" ")
    if parts:
        parts[-1] = req.word.upper()
    state["sentence"] = " ".join(parts) + " "
    return {"success": True}


@app.post("/clear")
def clear():
    state["sentence"]    = " "
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
            _update_suggestions(words[-1])
    return {"success": True}


@app.post("/toggle_gesture")
def toggle_gesture():
    state["gesture_control"] = not state["gesture_control"]
    state["gesture_action"]  = ""
    return {"gesture_control": state["gesture_control"]}


class TranslateRequest(BaseModel):
    text: str
    src:  str = "english"
    dest: str = "hindi"


def _autocorrect_sentence():
    """Autocorrect every word in state['sentence'] in-place. Returns corrected text."""
    words     = state["sentence"].strip().split(" ")
    corrected = []
    for w in words:
        if len(w.strip()) > 1:
            suggs = sym_spell.lookup(w, symspellpy.Verbosity.CLOSEST, max_edit_distance=2)
            corrected.append(suggs[0].term.upper() if suggs else w)
        else:
            corrected.append(w)
    state["sentence"] = " ".join(corrected) + " "
    return state["sentence"]


@app.post("/autocorrect")
def autocorrect():
    return {"sentence": _autocorrect_sentence()}


@app.post("/translate")
def translate(req: TranslateRequest):
    _autocorrect_sentence()
    try:
        translated = GoogleTranslator(source=req.src, target=req.dest).translate(
            state["sentence"].strip()
        )
        return {"translated": translated}
    except Exception as e:
        return {"error": str(e)}


# -------------------------
# TTS  (lazy imports — don't pay startup cost until first speak)
# -------------------------

class SpeakRequest(BaseModel):
    text:   str
    gender: str   = "Male"
    speed:  float = 1.0


@app.post("/speak")
async def speak(req: SpeakRequest):
    clean = req.text.strip()
    if state["is_speaking"] or len(clean) < 2:
        return {"success": False, "reason": "Too short or already speaking"}
    state["is_speaking"] = True

    async def _speak():
        try:
            from langdetect import detect
            try:
                lang = detect(clean)
            except Exception:
                lang = "en"

            tmp = os.path.join(os.path.dirname(__file__), "temp_tts.mp3")

            if lang == "hi":
                from gtts import gTTS
                import pygame
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                gTTS(text=clean, lang='hi').save(tmp)
                pygame.mixer.music.load(tmp)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)
                pygame.mixer.music.unload()
            else:
                voice = 'en-US-ChristopherNeural' if req.gender == "Male" else 'en-US-JennyNeural'
                rate  = f"+{int((req.speed - 1.0) * 100)}%" if req.speed > 1 else "+0%"
                comm  = edge_tts.Communicate(clean, voice, rate=rate)
                await comm.save(tmp)

                # pygame handles mp3 playback on all platforms — no OS shell needed
                import pygame
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(tmp)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)
                pygame.mixer.music.unload()

        except Exception as e:
            print(f"[TTS Error] {e}")
        finally:
            state["is_speaking"] = False
            tmp_path = os.path.join(os.path.dirname(__file__), "temp_tts.mp3")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    asyncio.create_task(_speak())
    return {"success": True}


# -------------------------
# ENTRY POINT
# -------------------------

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        # One worker is correct — the camera loop is a daemon thread, not a process
        workers=1,
        # Disable access log to cut console I/O on every MJPEG chunk request
        access_log=False,
    )

