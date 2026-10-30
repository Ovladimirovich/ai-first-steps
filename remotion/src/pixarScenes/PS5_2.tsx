import { useCurrentFrame } from "remotion";
import { PixarCard, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

const ROLES: [string, string, string][] = [
  ["🎮", "Архитектор миров", "придумываешь миры — ИИ строит"],
  ["🔬", "Исследователь", "ищешь лекарства с ИИ"],
  ["🎨", "Режиссёр-одиночка", "один делаешь мульт как студия"],
];

export const PS5_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number, fr = 0) => Math.round(((lines[i]?.start ?? 0) + ((lines[i]?.end ?? 0) - (lines[i]?.start ?? 0)) * fr - sceneStart) * 30);
  return (
    <>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(1000px 500px at 50% 0%, #E0F7FF 0%, #FFF6E0 55%, #FFE9B8 100%)" }} />
      <PixarTitle light>Три новые роли</PixarTitle>
      {ROLES.map(([ic, title, sub], i) => (
        <div key={title} style={{
          position: "absolute", left: 90 + i * 620, top: 220, width: 560, height: 380,
          background: "#fff", borderRadius: 32, padding: 28,
          boxShadow: "0 22px 50px rgba(0,0,0,.18), inset 0 1px 0 #fff",
          opacity: f > d(0) + i * 18 ? 1 : 0, transform: `translateY(${f > d(0) + i * 18 ? 0 : 24}px)`,
          transition: "all .4s",
          display: "grid", placeItems: "center", textAlign: "center",
          border: "2px solid rgba(255,255,255,.9)",
        }}>
          <div>
            <div style={{ fontSize: 72 }}>{ic}</div>
            <div style={{ fontFamily: "Montserrat, Arial", fontWeight: 800, fontSize: 28, color: "#1B2A4A", marginTop: 8 }}>{title}</div>
            <div style={{ fontFamily: "Montserrat, Arial", fontSize: 20, color: "#5A3A2A", marginTop: 8 }}>{sub}</div>
          </div>
        </div>
      ))}
      {f > d(1) && <PixarCard x={90} y={680} w={1740} delay={d(1)} bg="#243A66" size={28}>Один школьник с ИИ уже делает то, на что раньше нужна <span style={{ color: "#FFD23F", fontWeight: 800 }}>целая команда</span></PixarCard>}
    </>
  );
};
