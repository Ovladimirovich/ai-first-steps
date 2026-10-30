import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

// Pixar-спальня: теплый свет, стопка тетрадей, планшет
export const PS0_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  const stackH = interpolate(f, [0, 60], [0, 1], { extrapolateRight: "clamp" });
  // parallax фона
  const bgShift = interpolate(f, [0, 400], [0, -30], { extrapolateRight: "clamp" });
  return (
    <>
      {/* Pixar фон - теплая комната, свет из окна */}
      <div style={{
        position: "absolute", inset: 0,
        background: `
          radial-gradient(1200px 600px at 70% 20%, #FFF6E0 0%, #FFE9B8 28%, #FFD6A0 45%, transparent 70%),
          linear-gradient(180deg, #FFFDF5 0%, #FFF6E0 35%, #FFE5B8 100%)
        `,
        transform: `translateX(${bgShift}px)`,
      }} />
      {/* окно */}
      <div style={{
        position: "absolute", left: 1120, top: 0, width: 520, height: 520,
        background: "linear-gradient(180deg, #CDEEFF 0%, #8ECFFF 45%, #FFF 100%)",
        borderLeft: "18px solid #D9B56A", borderRight: "18px solid #D9B56A", borderBottom: "22px solid #D9B56A",
        boxShadow: "0 30px 60px rgba(0,0,0,.18), inset 0 0 40px rgba(255,255,255,.6)",
        opacity: 0.95,
      }}>
        <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 14, background: "#D9B56A" }} />
        <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: 14, background: "#D9B56A" }} />
      </div>
      {/* стол дерево */}
      <div style={{
        position: "absolute", left: 0, right: 0, top: 680, height: 400,
        background: "linear-gradient(180deg, #E8C99B 0%, #C9A86A 30%, #A88340 100%)",
        boxShadow: "0 -8px 30px rgba(0,0,0,.18)",
      }} />

      <PixarTitle light>Гора домашки</PixarTitle>

      {/* стопка тетрадей Pixar */}
      <div style={{
        position: "absolute", left: 120, top: 200, width: 520, height: 420,
        transform: `translateY(${(1 - stackH) * 40}px) scale(${0.92 + 0.08 * stackH})`, opacity: stackH,
        filter: "drop-shadow(0 22px 30px rgba(0,0,0,.28))",
      }}>
        {[
          { bg: "#2EE6D6", label: "Сочинение", rot: -1.5 },
          { bg: "#FFD23F", label: "Математика", rot: 1.2 },
          { bg: "#FF6B6B", label: "История", rot: -0.8 },
        ].map((b, i) => (
          <div key={i} style={{
            position: "absolute", left: 20 + i * 6, top: 320 - i * 48, width: 460, height: 92,
            background: b.bg, borderRadius: 16, transform: `rotate(${b.rot}deg)`,
            boxShadow: "0 6px 18px rgba(0,0,0,.18), inset 0 2px 0 rgba(255,255,255,.5), inset 0 -6px 12px rgba(0,0,0,.14)",
            display: "grid", placeItems: "center", fontFamily: "Montserrat, Arial", fontWeight: 800, fontSize: 28, color: "#0d1526",
            border: "2px solid rgba(255,255,255,.4)",
          }}>{b.label}</div>
        ))}
        <div style={{
          position: "absolute", left: 320, top: 20, width: 180, height: 120, background: "#fff",
          borderRadius: 18, transform: "rotate(4deg)", boxShadow: "0 12px 28px rgba(0,0,0,.22)",
          display: "grid", placeItems: "center", fontSize: 56,
        }}>😫</div>
      </div>

      {/* планшет */}
      <div style={{
        position: "absolute", left: 740, top: 280, width: 420, height: 280, background: "#0D1526",
        borderRadius: 22, padding: 16, boxShadow: "0 20px 50px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.2)",
        transform: `translateY(${interpolate(f, [30, 80], [30, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}px)`,
        opacity: interpolate(f, [30, 80], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
      }}>
        <div style={{ background: "#FFFDF5", borderRadius: 14, height: "100%", padding: 18, fontFamily: "Montserrat, Arial", fontSize: 22, lineHeight: 1.4, color: "#1B2A4A" }}>
          <div style={{ fontWeight: 800, marginBottom: 8 }}>Сочинение: мой любимый город будущего</div>
          <div style={{ background: "#FFE9B8", height: 10, borderRadius: 5, width: "70%", marginBottom: 10 }} />
          <div style={{ background: "#E8EEF6", height: 10, borderRadius: 5, width: "90%", marginBottom: 8 }} />
          <div style={{ background: "#E8EEF6", height: 10, borderRadius: 5, width: "84%", marginBottom: 8 }} />
          <div style={{ color: "#FF6B6B", fontWeight: 700, marginTop: 18 }}>▌</div>
        </div>
      </div>

      {f > d(1) && <PixarCard x={120} y={720} w={820} delay={d(1)} bg="#243A66" size={30}>А давай <PixarHL>сделаем вместе с ИИ?</PixarHL> За десять минут?</PixarCard>}
      {f > d(2) && <PixarCard x={120} y={860} w={520} delay={d(2)} bg="#1f5e46" size={34}>За десять?! 😲</PixarCard>}
    </>
  );
};
