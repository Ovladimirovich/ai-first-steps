import { interpolate, useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import { Cat } from "../components/Cat";
import type { SceneProps } from "../scenes";

export const PS2_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number, fr = 0) => Math.round(((lines[i]?.start ?? 0) + ((lines[i]?.end ?? 0) - (lines[i]?.start ?? 0)) * fr - sceneStart) * 30);
  const p = interpolate(f, [d(0, 0.12), d(0, 0.92)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const step = Math.round(1 + 49 * p);
  const ease = p * p;
  return (
    <>
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 55%, #FFD6A0 100%)" }} />
      <PixarTitle light>Из шума — шаг за шагом</PixarTitle>

      {/* стол мастерской */}
      <div style={{
        position: "absolute", left: 90, top: 190, width: 600, height: 600, borderRadius: 32,
        background: "#C9A86A", boxShadow: "0 30px 60px rgba(0,0,0,.22), inset 0 8px 18px rgba(255,255,255,.35)",
        padding: 18,
      }}>
        <div style={{ width: "100%", height: "100%", borderRadius: 24, overflow: "hidden", background: "#000", position: "relative" }}>
          <Cat style={{
            width: "100%", height: "100%", display: "block",
            filter: `blur(${(1 - ease) * 20}px) saturate(${0.35 + 0.65 * ease}) brightness(${0.85 + 0.15 * ease})`,
          }} />
          <svg width="100%" height="100%" style={{ position: "absolute", left: 0, top: 0, opacity: 1 - ease }}>
            <filter id="pixarNoise"><feTurbulence type="fractalNoise" baseFrequency="0.88" numOctaves="1" seed={f % 97} stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /></filter>
            <rect width="100%" height="100%" filter="url(#pixarNoise)" />
          </svg>
        </div>
      </div>

      <PixarCard x={730} y={200} w={520} size={28}>Шаг <b style={{ color: "#FFD23F", fontSize: 56 }}>{step}</b> / 50
        <div style={{ height: 14, background: "#1B2A4A", borderRadius: 7, marginTop: 12, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${p * 100}%`, background: "linear-gradient(90deg, #2EE6D6, #FFD23F)", borderRadius: 7 }} />
        </div>
      </PixarCard>
      <PixarCard x={730} y={400} w={520} size={26}>«На что это похоже, если тут<br />должен быть <PixarHL>кот-космонавт</PixarHL>?»</PixarCard>
      {f > d(1) && <PixarCard x={730} y={600} w={520} size={26} delay={d(1)} bg="#1f5e46">Как в Pixar-кино — только<br />кадра <PixarHL>не существовало</PixarHL> ✏️</PixarCard>}
    </>
  );
};
