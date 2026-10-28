import { interpolate, useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
export const S2_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const big = lines.find((l) => l.text.startsWith("Миллиарды"));
  const bf = big ? (big.start - sceneStart) * 30 : 1e9;
  const zoom = interpolate(f, [bf - 60, bf + 30], [1, 0.3], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const n = 8, rows = 6;
  return (
    <>
      <Title>Внутри модели — ручки</Title>
      <div style={{ position: "absolute", left: 140, top: 220, width: 760, height: 540, transformOrigin: "top left", transform: `scale(${zoom})` }}>
        {Array.from({ length: n * rows * (zoom < 0.5 ? 16 : 1) }).map((_, i) => (
          <div key={i} style={{ position: "absolute", left: (i % (n * (zoom < 0.5 ? 4 : 1))) * 95, top: Math.floor(i / (n * (zoom < 0.5 ? 4 : 1))) * 95, width: 70, height: 70, borderRadius: 35, background: "#3a5590", border: "5px solid #2EE6D6" }}>
            <div style={{ position: "absolute", left: 31, top: 6, width: 6, height: 26, background: "#FFD23F", transformOrigin: "3px 26px", transform: `rotate(${(f * 7 + i * 40) % 360}deg)` }} />
          </div>
        ))}
      </div>
      {f > bf && <Card x={140} y={660} w={760} size={54}>Ручек — <HL>миллиарды</HL></Card>}
    </>
  );
};
