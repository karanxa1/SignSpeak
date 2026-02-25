import { useState, useEffect, useRef } from "react";

const API = "http://localhost:8000";
const WS = "ws://localhost:8000/ws";

export default function App() {
  const [state, setState] = useState({
    sentence: "",
    character: "",
    confidence: 0,
    suggestions: ["", "", "", ""],
    is_speaking: false,
    gesture_control: false,
    gesture_action: "",
  });
  const [translated, setTranslated] = useState("");
  const [busy, setBusy] = useState(false);
  const [dark, setDark] = useState(false);
  const [listening, setListening] = useState(false);
  const prevGesture = useRef("");

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS);
      ws.onmessage = (e) => setState((p) => ({ ...p, ...JSON.parse(e.data) }));
      ws.onclose = () => setTimeout(connect, 1000);
      return ws;
    };
    const ws = connect();
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (!state.gesture_control || !state.gesture_action) return;
    if (state.gesture_action === prevGesture.current) return;
    prevGesture.current = state.gesture_action;
    if (state.gesture_action === "translate") translate();
    else if (state.gesture_action === "clear") clear();
    else if (state.gesture_action === "speak") speak(state.sentence);
  }, [state.gesture_action, state.gesture_control]);

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [dark]);

  const post = async (path, body) => {
    const r = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return r.json();
  };

  const clear = () => { post("/clear"); setTranslated(""); };
  const appendPhrase = (phrase) => { post("/append_text", { text: phrase }); };
  const startVoiceInput = () => {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      alert("Speech recognition not supported in this browser. Try Chrome or Edge.");
      return;
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new Recognition();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = "en-US";
    rec.onstart = () => setListening(true);
    rec.onend = () => setListening(false);
    rec.onresult = (e) => {
      const t = e.results[0][0].transcript;
      if (t) post("/append_text", { text: t });
    };
    rec.onerror = () => setListening(false);
    rec.start();
  };
  const translate = async () => {
    if (!state.sentence.trim()) return;
    setBusy(true);
    const d = await post("/translate", { text: state.sentence.trim(), src: "english", dest: "hindi" });
    if (d.translated) setTranslated(d.translated);
    setBusy(false);
  };
  const speak = (text) => { if (text && text.trim().length > 1) post("/speak", { text, gender: "Male", speed: 1.0 }); };
  const applySuggestion = (w) => { if (w.trim()) post("/apply_suggestion", { word: w }); };
  const toggleGesture = () => post("/toggle_gesture");

  const conf = state.confidence || 0;

  const bg = dark ? "bg-neutral-950 text-neutral-100" : "bg-white text-black";
  const border = dark ? "border-neutral-700" : "border-neutral-200";
  const borderStrong = dark ? "border-neutral-500" : "border-black";
  const muted = dark ? "text-neutral-500" : "text-neutral-400";
  const card = dark ? "bg-neutral-900" : "bg-neutral-50";
  const btnPrimary = dark ? "bg-white text-black hover:bg-neutral-200" : "bg-black text-white hover:bg-neutral-800";
  const btnOutline = dark
    ? "border-neutral-500 text-neutral-200 hover:bg-white hover:text-black"
    : "border-black hover:bg-black hover:text-white";
  const btnGhost = dark
    ? "border-neutral-700 text-neutral-500 hover:border-neutral-400 hover:text-neutral-200"
    : "border-neutral-300 text-neutral-500 hover:border-black hover:text-black";
  const confBar = dark ? "bg-neutral-700" : "bg-neutral-200";
  const confFill = dark ? "bg-white" : "bg-black";
  const confColor = conf > 75 ? (dark ? "#fff" : "#000") : conf > 40 ? "#888" : "#bbb";

  return (
    <div className={`min-h-screen font-sans px-4 py-4 sm:p-6 md:p-10 max-w-7xl mx-auto transition-colors duration-300 overflow-x-hidden ${bg}`}>

      {/* Header */}
      <header className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b pb-4 mb-4 sm:mb-8 ${borderStrong}`}>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">SignSpeak</h1>
        <div className="flex gap-2 sm:gap-3">
          <button onClick={() => setDark(!dark)}
            className={`min-h-[44px] sm:min-h-0 text-xs tracking-widest uppercase px-4 py-2.5 sm:px-3 sm:py-1.5 border rounded-lg active:scale-[0.98] transition-all touch-manipulation ${btnGhost}`}>
            {dark ? "☀ Light" : "● Dark"}
          </button>
          <button onClick={toggleGesture}
            className={`min-h-[44px] sm:min-h-0 text-xs tracking-widest uppercase px-4 py-2.5 sm:px-3 sm:py-1.5 border rounded-lg active:scale-[0.98] transition-all touch-manipulation ${
              state.gesture_control
                ? btnPrimary + " border-transparent"
                : btnGhost
            }`}>
            {state.gesture_control ? "✋ ON" : "Gesture"}
          </button>
        </div>
      </header>

      {/* Gesture Banner */}
      {state.gesture_control && (
        <div className={`mb-4 sm:mb-6 border rounded-lg p-3 sm:p-4 text-sm ${border} ${card}`}>
          <p className="font-semibold mb-1">Gesture Control Active</p>
          <p className={`text-xs sm:text-sm ${muted}`}>
            👍 Translate &nbsp; ✌️ Speak &nbsp; 🖐 Clear
          </p>
          {state.gesture_action && (
            <p className="mt-2 font-mono text-xs">Action: <span className="font-semibold">{state.gesture_action}</span></p>
          )}
        </div>
      )}

      {/* Feeds */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6 mb-4 sm:mb-8">
        <div>
          <p className={`text-[10px] sm:text-[11px] uppercase tracking-widest mb-1.5 sm:mb-2 ${muted}`}>Camera</p>
          <div className={`border rounded-lg overflow-hidden aspect-video ${border} ${card}`}>
            <img src={`${API}/video_feed`} className="w-full h-full object-cover" alt="Camera" />
          </div>
        </div>
        <div>
          <p className={`text-[10px] sm:text-[11px] uppercase tracking-widest mb-1.5 sm:mb-2 ${muted}`}>Hand Tracking</p>
          <div className={`border rounded-lg overflow-hidden aspect-video flex items-center justify-center ${border} ${dark ? "bg-neutral-800" : "bg-neutral-100"}`}>
            <img src={`${API}/skeleton_feed`} className="h-full object-contain" alt="Skeleton" />
          </div>
        </div>
      </section>

      {/* Detected + Confidence + Suggestions */}
      <section className={`flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6 mb-4 sm:mb-8 border rounded-lg p-4 sm:p-5 ${border}`}>
        <div className="flex items-center gap-4 sm:shrink-0">
          <div>
            <p className={`text-[10px] sm:text-[11px] uppercase tracking-widest mb-1 ${muted}`}>Detected</p>
            <div className={`w-12 h-12 sm:w-14 sm:h-14 border-2 rounded-lg flex items-center justify-center text-2xl sm:text-3xl font-bold ${borderStrong}`}>
              {state.character || "—"}
            </div>
          </div>
          <div className="sm:w-20">
            <p className={`text-[10px] sm:text-[11px] uppercase tracking-widest mb-1 ${muted}`}>Confidence</p>
            <div className="flex items-end gap-1">
              <span className="text-xl sm:text-2xl font-bold tabular-nums" style={{ color: confColor }}>{conf}</span>
              <span className={`text-xs mb-1 ${muted}`}>%</span>
            </div>
            <div className={`w-20 sm:w-full h-1.5 sm:h-1 rounded-full mt-1 overflow-hidden ${confBar}`}>
              <div className={`h-full rounded-full transition-all duration-200 ${confFill}`} style={{ width: `${conf}%` }} />
            </div>
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-[10px] sm:text-[11px] uppercase tracking-widest mb-2 ${muted}`}>Suggestions</p>
          <div className="flex flex-wrap gap-2">
            {state.suggestions.map((w, i) => (
              <button key={i} onClick={() => applySuggestion(w)} disabled={!w.trim()}
                className={`min-h-[44px] sm:min-h-0 px-4 py-2.5 sm:px-3 sm:py-1.5 text-sm border rounded-lg active:scale-[0.98] transition-all touch-manipulation disabled:opacity-30 disabled:cursor-default disabled:active:scale-100 ${btnOutline}`}>
                {w.trim() || "—"}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Phrase Shortcuts */}
      <section className="mb-4 sm:mb-6">
        <p className={`text-[10px] sm:text-[11px] uppercase tracking-widest mb-2 ${muted}`}>Quick Phrases</p>
        <div className="flex flex-wrap gap-2">
          {["Hello", "Thank you", "Help"].map((p) => (
            <button key={p} onClick={() => appendPhrase(p)}
              className={`min-h-[44px] sm:min-h-0 px-4 py-2.5 sm:px-3 sm:py-1.5 text-sm border rounded-lg active:scale-[0.98] transition-all touch-manipulation ${btnOutline}`}>
              {p}
            </button>
          ))}
        </div>
      </section>

      {/* Output */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6 mb-4 sm:mb-8">
        <div>
          <p className={`text-[10px] sm:text-[11px] uppercase tracking-widest mb-1.5 sm:mb-2 ${muted}`}>Sentence</p>
          <div className={`border rounded-lg p-3 sm:p-4 min-h-[72px] sm:min-h-[80px] text-base sm:text-lg font-medium ${border}`}>
            {state.sentence.trim() || <span className={`font-normal ${muted}`}>Waiting for signs…</span>}
          </div>
        </div>
        <div>
          <p className={`text-[10px] sm:text-[11px] uppercase tracking-widest mb-1.5 sm:mb-2 ${muted}`}>Translation</p>
          <div className={`border rounded-lg p-3 sm:p-4 min-h-[72px] sm:min-h-[80px] text-base sm:text-lg font-medium ${border}`}>
            {translated || <span className={`font-normal ${muted}`}>—</span>}
          </div>
        </div>
      </section>

      {/* Controls */}
      <section className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 sm:gap-3">
        <button onClick={startVoiceInput} disabled={listening}
          className={`col-span-2 sm:col-span-1 min-h-[48px] sm:min-h-0 px-4 py-3 sm:px-5 sm:py-2.5 border text-sm font-medium rounded-lg active:scale-[0.98] transition-all touch-manipulation ${listening ? "opacity-60" : ""} ${btnOutline}`}
          title="Speak to add text">
          {listening ? "Listening…" : "🎤 Voice"}
        </button>
        <button onClick={translate} disabled={busy || !state.sentence.trim()}
          className={`min-h-[48px] sm:min-h-0 px-4 py-3 sm:px-5 sm:py-2.5 text-sm font-medium rounded-lg active:scale-[0.98] transition-all touch-manipulation disabled:opacity-40 ${btnPrimary}`}>
          {busy ? "Translating…" : "Translate"}
        </button>
        <button onClick={() => speak(state.sentence)} disabled={state.is_speaking || !state.sentence.trim()}
          className={`min-h-[48px] sm:min-h-0 px-4 py-3 sm:px-5 sm:py-2.5 border text-sm font-medium rounded-lg active:scale-[0.98] transition-all touch-manipulation disabled:opacity-40 ${btnOutline}`}
          title="Speak English">
          <span className="hidden sm:inline">Speak Original</span>
          <span className="sm:hidden">Speak EN</span>
        </button>
        <button onClick={() => speak(translated)} disabled={state.is_speaking || !translated}
          className={`min-h-[48px] sm:min-h-0 px-4 py-3 sm:px-5 sm:py-2.5 border text-sm font-medium rounded-lg active:scale-[0.98] transition-all touch-manipulation disabled:opacity-40 ${btnOutline}`}
          title="Speak Hindi">
          <span className="hidden sm:inline">Speak Translation</span>
          <span className="sm:hidden">Speak HI</span>
        </button>
        <button onClick={clear}
          className={`col-span-2 sm:col-span-1 sm:ml-auto min-h-[48px] sm:min-h-0 px-4 py-3 sm:px-5 sm:py-2.5 border text-sm font-medium rounded-lg active:scale-[0.98] transition-all touch-manipulation ${btnGhost}`}>
          Clear
        </button>
      </section>
    </div>
  );
}
