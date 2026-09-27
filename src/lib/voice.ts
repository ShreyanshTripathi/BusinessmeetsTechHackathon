type Item = { id: string; text: string; critical: boolean };

const queue: Item[] = [];
let speaking = false;
let enabled = false;

export function setVoiceEnabled(v: boolean) {
  enabled = v;
  if (!v && typeof window !== "undefined" && "speechSynthesis" in window) {
    queue.length = 0;
    window.speechSynthesis.cancel();
    speaking = false;
  }
}
export const voiceSupported = () => typeof window !== "undefined" && "speechSynthesis" in window;

function pickVoice(): SpeechSynthesisVoice | undefined {
  const vs = window.speechSynthesis.getVoices();
  return vs.find((v) => v.lang === "en-US") ?? vs.find((v) => v.lang.startsWith("en"));
}

function next() {
  if (speaking || !enabled || !voiceSupported()) return;
  const item = queue.shift();
  if (!item) return;
  speaking = true;
  const u = new SpeechSynthesisUtterance(item.text);
  u.rate = 1.05;
  u.lang = "en-US";
  const v = pickVoice();
  if (v) u.voice = v;
  u.onend = u.onerror = () => { speaking = false; next(); };
  window.speechSynthesis.speak(u);
}

export function announce(id: string, text: string, critical: boolean, force = false) {
  if ((!enabled && !force) || !voiceSupported()) return;
  if (queue.some((q) => q.id === id)) return;
  const item = { id, text, critical };
  if (critical) {
    const idx = queue.findIndex((q) => !q.critical);
    if (idx === -1) queue.push(item); else queue.splice(idx, 0, item);
  } else queue.push(item);
  if (force && !enabled) { enabled = true; next(); enabled = false; return; }
  next();
}

export function dropFromQueue(id: string) {
  const i = queue.findIndex((q) => q.id === id);
  if (i >= 0) queue.splice(i, 1);
}
