import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { SceneProps } from ".";
const topics = [["🧠", "Что такое ИИ"], ["🎛", "Что такое модель"], ["💬", "ChatGPT · Алиса · GigaChat"], ["🎨", "Картинки, видео, музыка"]];
export const S0_2: React.FC<SceneProps> = () => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 10 } });
  return (
    <>
      <div style={{ position: "absolute", left: 0, right: 0, top: 120, textAlign: "center", fontFamily: "Montserrat, Arial", fontWeight: 800, fontSize: 96, color: "#fff", transform: `scale(${s})` }}>Первые шаги в <span style={{ color: "#2EE6D6" }}>ИИ</span></div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 250, textAlign: "center", fontFamily: "Montserrat, Arial", fontSize: 34, color: "#FFD23F", opacity: s }}>для 5–8 классов · 11 минут</div>
      {topics.map(([ic, t], i) => {
        const o = interpolate(f, [30 + i * 40, 50 + i * 40], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return <div key={t} style={{ position: "absolute", left: 160 + i * 240, top: 380, width: 220, height: 200, background: "#243A66", borderRadius: 24, display: "grid", placeItems: "center", textAlign: "center", fontFamily: "Montserrat, Arial", fontSize: 24, color: "#fff", opacity: o, transform: `translateY(${(1 - o) * 30}px)` }}><div style={{ fontSize: 56 }}>{ic}</div>{t}</div>;
      })}
    </>
  );
};
