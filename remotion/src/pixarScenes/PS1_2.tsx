import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

// Pixar-пиццерия вместо доски: Солнце-повар
export const PS1_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number, fr = 0) => Math.round(((lines[i]?.start ?? 0) + ((lines[i]?.end ?? 0) - (lines[i]?.start ?? 0)) * fr - sceneStart) * 30);
  const typed = "Объясни фотосинтез как для 5 класса, на примере пиццерии".slice(0, Math.max(0, Math.floor((f - d(0)) / 1.6)));
  const reveal = interpolate(f, [d(1), d(1) + 50], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <>
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)" }} />
      <PixarTitle light>Объясни как для друга</PixarTitle>

      {/* промпт-планшет */}
      <div style={{
        position: "absolute", left: 90, top: 170, width: 880, background: "#0D1526", borderRadius: 20, padding: 16,
        boxShadow: "0 18px 40px rgba(0,0,0,.28)", fontFamily: "monospace", color: "#2EE6D6", fontSize: 24,
      }}>
        › {typed}{f % 22 < 11 ? "▌" : " "}
      </div>

      {/* Pixar-пиццерия */}
      <div style={{
        position: "absolute", left: 90, top: 300, width: 880, height: 440, background: "#fff",
        borderRadius: 28, overflow: "hidden", boxShadow: "0 20px 50px rgba(0,0,0,.18)",
        opacity: reveal, transform: `scale(${0.96 + 0.04 * reveal})`,
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0,
      }}>
        <div style={{ background: "#FFF0C9", display: "grid", placeItems: "center", padding: 20 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 86 }}>☀️</div>
            <div style={{ fontFamily: "Montserrat, Arial", fontWeight: 800, fontSize: 22, color: "#1B2A4A" }}>Солнце — повар</div>
            <div style={{ fontSize: 16, color: "#5A3A2A" }}>даёт свет и тепло</div>
          </div>
        </div>
        <div style={{ background: "#E0FFF4", display: "grid", placeItems: "center", padding: 20 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 86 }}>🌿</div>
            <div style={{ fontFamily: "Montserrat, Arial", fontWeight: 800, fontSize: 22, color: "#1B2A4A" }}>Лист — кухня</div>
            <div style={{ fontSize: 16, color: "#5A3A2A" }}>готовит сахар из солнца + воды</div>
          </div>
        </div>
        <div style={{ background: "#FFE9E9", display: "grid", placeItems: "center", padding: 20 }}>
          <div style={{ fontSize: 64 }}>🍕</div>
          <div style={{ fontFamily: "Montserrat, Arial", fontWeight: 700, fontSize: 18, color: "#1B2A4A" }}>Сахар = энергия пиццы</div>
        </div>
        <div style={{ background: "#E8E0FF", display: "grid", placeItems: "center", padding: 20 }}>
          <div style={{ fontSize: 64 }}>😋</div>
          <div style={{ fontFamily: "Montserrat, Arial", fontWeight: 700, fontSize: 18, color: "#1B2A4A" }}>Растение растёт и делится</div>
        </div>
      </div>

      <PixarCard x={1020} y={220} w={820} delay={d(1)} bg="#243A66" size={30}>Попроси <PixarHL>"как для друга"</PixarHL>,<br />"через мем" или "через игру".<br />ИИ подстроится под <PixarHL>тебя</PixarHL>.</PixarCard>
      {f > d(2) && <PixarCard x={1020} y={520} w={820} delay={d(2)} bg="#1f5e46" size={30}>Попробуй: "объясни гравитацию<br />через Minecraft" 🎮</PixarCard>}
    </>
  );
};
