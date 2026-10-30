import { useCurrentFrame } from "remotion";
import { PixarCard, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS6_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const d = (i: number, fr = 0) => Math.round(((lines[i]?.start ?? 0) + ((lines[i]?.end ?? 0) - (lines[i]?.start ?? 0)) * fr - sceneStart) * 30);
  const f = useCurrentFrame();
  const shields = [
    { ic: "🔍", title: "Проверяй", sub: "2 источника + учебник", bg: "#2EE6D6", delay: d(0) },
    { ic: "✍️", title: "Указывай", sub: "сделано с ИИ", bg: "#FFD23F", delay: d(1) },
    { ic: "🔒", title: "Береги", sub: "без адресов и паролей", bg: "#FF6B6B", delay: d(2) },
  ];
  return (
    <>
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)" }} />
      <PixarTitle light>Три правила Pixar-игры</PixarTitle>
      {shields.map((s) => (
        <div key={s.title} style={{
          position: "absolute", left: s.title === "Проверяй" ? 90 : s.title === "Указывай" ? 700 : 1310,
          top: 210, width: 520, height: 420, background: s.bg, borderRadius: 32,
          display: "grid", placeItems: "center", textAlign: "center",
          boxShadow: "0 22px 50px rgba(0,0,0,.2), inset 0 8px 18px rgba(255,255,255,.4), inset 0 -8px 18px rgba(0,0,0,.14)",
          opacity: f > s.delay ? 1 : 0, transform: `scale(${f > s.delay ? 1 : 0.85})`,
          border: "2px solid rgba(255,255,255,.5)",
        }}>
          <div>
            <div style={{ fontSize: 72, filter: "drop-shadow(0 4px 10px rgba(0,0,0,.18))" }}>{s.ic}</div>
            <div style={{ fontFamily: "Montserrat, Arial", fontWeight: 800, fontSize: 36, color: "#0d1526", marginTop: 8 }}>{s.title}</div>
            <div style={{ fontFamily: "Montserrat, Arial", fontSize: 22, color: "#0d1526", opacity: 0.85 }}>{s.sub}</div>
          </div>
        </div>
      ))}
      {f > d(2) + 10 && <PixarCard x={90} y={710} w={1740} delay={d(2) + 10} bg="#243A66" size={26}>И спроси у родителей про возраст — у многих сервисов <span style={{ color: "#FFD23F", fontWeight: 800 }}>13+</span></PixarCard>}
    </>
  );
};
