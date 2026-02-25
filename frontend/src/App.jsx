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
    <div className={`min-h-screen font-sans p-6 md:p-10 max-w-7xl mx-auto transition-colors duration-300 ${bg}`}>

      {/* Header */}
      <header className={`flex items-baseline justify-between border-b pb-4 mb-8 ${borderStrong}`}>
        <h1 className="text-2xl font-semibold tracking-tight">SignSpeak</h1>
        <div className="flex items-center gap-3">
          <button onClick={() => setDark(!dark)}
            className={`text-xs tracking-widest uppercase px-3 py-1.5 border rounded transition-colors ${btnGhost}`}>
            {dark ? "☀ Light" : "● Dark"}
          </button>
          <button onClick={toggleGesture}
            className={`text-xs tracking-widest uppercase px-3 py-1.5 border rounded transition-colors ${
              state.gesture_control
                ? btnPrimary + " border-transparent"
                : btnGhost
            }`}>
            {state.gesture_control ? "✋ Gesture ON" : "Gesture Control"}
          </button>
        </div>
      </header>

      {/* Gesture Banner */}
      {state.gesture_control && (
        <div className={`mb-6 border rounded p-4 text-sm ${border} ${card}`}>
          <p className="font-semibold mb-1">Gesture Control Active</p>
          <p className={muted}>
            👍 Thumbs Up → Translate &nbsp; ✌️ Peace → Speak &nbsp; 🖐 Open Palm → Clear
          </p>
          {state.gesture_action && (
            <p className="mt-2 font-mono text-xs">Action: <span className="font-semibold">{state.gesture_action}</span></p>
          )}
        </div>
      )}

      {/* Feeds */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div>
          <p className={`text-[11px] uppercase tracking-widest mb-2 ${muted}`}>Camera</p>
          <div className={`border rounded overflow-hidden aspect-video ${border} ${card}`}>
            <img src={`${API}/video_feed`} className="w-full h-full object-cover" alt="Camera" />
          </div>
        </div>
        <div>
          <p className={`text-[11px] uppercase tracking-widest mb-2 ${muted}`}>Hand Tracking</p>
          <div className={`border rounded overflow-hidden aspect-video flex items-center justify-center ${border} ${dark ? "bg-neutral-800" : "bg-neutral-100"}`}>
            <img src={`${API}/skeleton_feed`} className="h-full object-contain" alt="Skeleton" />
          </div>
        </div>
      </section>

      {/* Detected + Confidence + Suggestions */}
      <section className={`flex items-center gap-6 mb-8 border rounded p-5 ${border}`}>
        <div className="shrink-0">
          <p className={`text-[11px] uppercase tracking-widest mb-1 ${muted}`}>Detected</p>
          <div className={`w-14 h-14 border-2 rounded flex items-center justify-center text-3xl font-bold ${borderStrong}`}>
            {state.character || "—"}
          </div>
        </div>
        <div className="shrink-0 w-20">
          <p className={`text-[11px] uppercase tracking-widest mb-1 ${muted}`}>Confidence</p>
          <div className="flex items-end gap-1">
            <span className="text-2xl font-bold tabular-nums" style={{ color: confColor }}>{conf}</span>
            <span className={`text-xs mb-1 ${muted}`}>%</span>
          </div>
          <div className={`w-full h-1 rounded-full mt-1 overflow-hidden ${confBar}`}>
            <div className={`h-full rounded-full transition-all duration-200 ${confFill}`} style={{ width: `${conf}%` }} />
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-[11px] uppercase tracking-widest mb-1 ${muted}`}>Suggestions</p>
          <div className="flex gap-2">
            {state.suggestions.map((w, i) => (
              <button key={i} onClick={() => applySuggestion(w)} disabled={!w.trim()}
                className={`px-3 py-1.5 text-sm border rounded transition-colors disabled:opacity-30 disabled:cursor-default ${btnOutline}`}>
                {w.trim() || "—"}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Phrase Shortcuts */}
      <section className="mb-6">
        <p className={`text-[11px] uppercase tracking-widest mb-2 ${muted}`}>Quick Phrases</p>
        <div className="flex flex-wrap gap-2">
          {["Hello", "Thank you", "Help"].map((p) => (
            <button key={p} onClick={() => appendPhrase(p)}
              className={`px-3 py-1.5 text-sm border rounded transition-colors ${btnOutline}`}>
              {p}
            </button>
          ))}
        </div>
      </section>

      {/* Output */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div>
          <p className={`text-[11px] uppercase tracking-widest mb-2 ${muted}`}>Sentence</p>
          <div className={`border rounded p-4 min-h-[80px] text-lg font-medium ${border}`}>
            {state.sentence.trim() || <span className={`font-normal ${muted}`}>Waiting for signs…</span>}
          </div>
        </div>
        <div>
          <p className={`text-[11px] uppercase tracking-widest mb-2 ${muted}`}>Translation</p>
          <div className={`border rounded p-4 min-h-[80px] text-lg font-medium ${border}`}>
            {translated || <span className={`font-normal ${muted}`}>—</span>}
          </div>
        </div>
      </section>

      {/* Controls */}
      <section className="flex flex-wrap gap-3">
        <button onClick={startVoiceInput} disabled={listening}
          className={`px-5 py-2.5 border text-sm font-medium rounded transition-colors ${listening ? "opacity-60" : ""} ${btnOutline}`}
          title="Speak to add text">
          {listening ? "Listening…" : "🎤 Voice Input"}
        </button>
        <button onClick={translate} disabled={busy || !state.sentence.trim()}
          className={`px-5 py-2.5 text-sm font-medium rounded transition-colors disabled:opacity-40 ${btnPrimary}`}>
          {busy ? "Translating…" : "Translate"}
        </button>
        <button onClick={() => speak(state.sentence)} disabled={state.is_speaking || !state.sentence.trim()}
          className={`px-5 py-2.5 border text-sm font-medium rounded transition-colors disabled:opacity-40 ${btnOutline}`}>
          Speak Original
        </button>
        <button onClick={() => speak(translated)} disabled={state.is_speaking || !translated}
          className={`px-5 py-2.5 border text-sm font-medium rounded transition-colors disabled:opacity-40 ${btnOutline}`}>
          Speak Translation
        </button>
        <button onClick={clear}
          className={`px-5 py-2.5 border text-sm font-medium rounded transition-colors ml-auto ${btnGhost}`}>
          Clear
        </button>
      </section>
    </div>
  );
}
