import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { PixarTitle } from "../components/PixarCard";

const ITEMS: [string, string][] = [
  ["🎓", "Репетитор"],
  ["🎨", "Творец"],
  ["🔍", "Исследователь"],
  ["🚀", "Профессия"],
];

export const PS0_2: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 12, stiffness: 90 } });
  return (
    <>
      <div style={{
        position: "absolute", inset: 0,
        background: "radial-gradient(1000px 600px at 50% 18%, #FFF6E0 0%, #FFE9B8 40%, #FFDAB0 100%)",
      }} />
      {/* облака Pixar */}
      <div style={{
        position: "absolute", left: 0, right: 0, top: 0, height: 520,
        background: `url(${`pixar/clouds_pixar_bg.jpg`}) center/cover`,
        opacity: 0.55,
      }} />
      <div style={{
        position: "absolute", left: "50%", top: 180, width: 900, height: 420, marginLeft: -450,
        background: "rgba(255,255,255,.72)", borderRadius: 36, backdropFilter: "blur(6px)",
        boxShadow: "0 30px 80px rgba(0,0,0,.18), inset 0 1px 0 #fff",
        transform: `scale(${s})`, display: "grid", placeItems: "center",
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontFamily: "Montserrat, Arial", fontWeight: 800, fontSize: 84, color: "#1B2A4A", letterSpacing: -1, lineHeight: 1 }}>
            Зачем ИИ <span style={{ color: "#FF6B6B" }}>школьнику</span>?
          </div>
          <div style={{ fontFamily: "Montserrat, Arial", fontSize: 32, color: "#5A3A2A", marginTop: 12, fontWeight: 700 }}>
            4 суперсилы · Pixar-версия · 11 минут
          </div>
          <div style={{ marginTop: 18, fontSize: 22, color: "#243A66" }}>с Битом и Машей</div>
        </div>
      </div>

      <PixarTitle> </PixarTitle>

      {ITEMS.map(([ic, t], i) => {
        const o = interpolate(f, [40 + i * 18, 70 + i * 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const y = interpolate(f, [40 + i * 18, 70 + i * 18], [40, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={t} style={{
            position: "absolute", left: 160 + i * 400, top: 660, width: 300, height: 240,
            background: "#fff", borderRadius: 28, display: "grid", placeItems: "center", textAlign: "center",
            fontFamily: "Montserrat, Arial", fontWeight: 800, fontSize: 26, color: "#1B2A4A",
            boxShadow: "0 18px 40px rgba(0,0,0,.18), inset 0 1px 0 #fff",
            opacity: o, transform: `translateY(${y}px)`,
            border: "2px solid rgba(255,255,255,.9)",
          }}>
            <div style={{ fontSize: 64 }}>{ic}</div>{t}
          </div>
        );
      })}
    </>
  );
};
