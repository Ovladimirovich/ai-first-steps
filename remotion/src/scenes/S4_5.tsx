import { interpolate, useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
const cars = [["ChatGPT", "#1f5e46"], ["Алиса AI", "#4a2f7a"], ["GigaChat", "#1f5a5a"]];
export const S4_5: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  return (
    <>
      <Title>Разные марки — один мотор</Title>
      <div style={{ position: "absolute", left: 0, top: 560, width: 1150, height: 12, background: "#3b4a7a" }} />
      {cars.map(([n, c], i) => {
        const x = interpolate(f, [d(0) + i * 12, d(0) + 60 + i * 12], [-500, 80 + i * 370], { extrapolateRight: "clamp" });
        return (
          <svg key={n} viewBox="0 0 300 160" style={{ position: "absolute", left: x, top: 350, width: 400 }}>
            <rect x="20" y="60" width="260" height="60" rx="18" fill={c} /><path d="M70 60 l30 -40 h100 l30 40z" fill={c} />
            <circle cx="80" cy="125" r="24" fill="#111" /><circle cx="220" cy="125" r="24" fill="#111" />
            <circle cx="80" cy="125" r="9" fill="#aab" /><circle cx="220" cy="125" r="9" fill="#aab" />
            <rect x="110" y="70" width="80" height="40" rx="8" fill="#FFD23F" opacity={f > d(0) + 70 ? 1 : 0} />
            <text x="150" y="97" textAnchor="middle" fontSize="18" fontWeight="800" fill="#1B2A4A" opacity={f > d(0) + 70 ? 1 : 0}>модель</text>
            <text x="150" y="150" textAnchor="middle" fontSize="22" fontWeight="800" fill="#fff">{n}</text>
          </svg>
        );
      })}
      {f > d(2) && <Card x={100} y={640} w={1000} delay={d(2)}>Какая лучше? <HL>Та, что решает твою задачу</HL>. Попробуй одно задание в двух ботах — и спроси у родителей</Card>}
    </>
  );
};
