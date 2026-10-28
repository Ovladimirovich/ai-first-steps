import { interpolate, useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
export const S2_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  const drops = Array.from({ length: 14 }, (_, i) => ({ x: 330 + (i * 37) % 360, y: ((f * 6 + i * 70) % 320) }));
  const glow = interpolate(f, [0, 240], [0.2, 1], { extrapolateRight: "clamp" });
  return (
    <>
      <Title>Что такое модель</Title>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1920, height: 1080, background: "radial-gradient(circle at 540px 560px, #243A66 0%, #1B2A4A 45%)" }} />
      {drops.map((p, i) => <div key={i} style={{ position: "absolute", left: p.x, top: 140 + p.y, width: 14, height: 22, borderRadius: "50% 50% 50% 50% / 60% 60% 40% 40%", background: "#FFD23F", opacity: p.y < 300 ? 0.9 : 0 }} />)}
      <svg viewBox="0 0 400 240" style={{ position: "absolute", left: 300, top: 470, width: 480 }}>
        <path d="M20 60 q40 -50 90 -20 q50 -50 110 -10 q60 -40 110 10 q60 10 50 70 q30 60 -30 90 q-30 60 -100 40 q-60 40 -120 0 q-80 20 -100 -40 q-40 -50 -10 -80 q-20 -50 0 -60z" fill="#2EE6D6" opacity={0.85} />
        {Array.from({ length: 30 }, (_, i) => <circle key={i} cx={40 + (i * 53) % 320} cy={50 + (i * 37) % 150} r={5 + (i % 3) * 3} fill="#FFD23F" opacity={glow * (0.4 + 0.6 * Math.abs(Math.sin(f / 9 + i)))} />)}
      </svg>
      <Card x={960} y={300} w={760} delay={d(0)}>Модель — <HL>губка</HL>: впитывает закономерности из примеров</Card>
      <Card x={960} y={520} w={760} delay={d(1)} bg="#3a2a4a">И что внутри губки? 🤔</Card>
    </>
  );
};
