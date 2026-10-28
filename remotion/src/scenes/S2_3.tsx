import { interpolate, useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
const opts = [["раму", 87, "#2EE6D6"], ["посуду", 9, "#FFD23F"], ["слона", 0.1, "#FF6B6B"]] as const;
export const S2_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  const answered = f > d(3);
  const bars = interpolate(f - d(2) - 20, [0, 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <>
      <Title>Игра: угадай следующее слово</Title>
      <Card x={140} y={220} w={900} size={64} delay={d(2)}>Мама мыла <HL>{answered ? "раму" : "…"}</HL></Card>
      <Card x={140} y={400} w={900} delay={d(2) + 10}>
        {opts.map(([w, p, c]) => (
          <div key={w} style={{ display: "flex", alignItems: "center", gap: 20, margin: "14px 0" }}>
            <span style={{ width: 170 }}>{w}</span>
            <div style={{ height: 34, width: Math.max(6, 560 * (p / 100) * bars), background: c, borderRadius: 8 }} />
            <b>{p}%</b>
          </div>
        ))}
      </Card>
      {f > d(4) && <Card x={140} y={740} w={900} delay={d(4)} bg="#3a2a4a">Угадала → ручки <HL>+</HL> · ошиблась → ручки <HL>−</HL></Card>}
    </>
  );
};
