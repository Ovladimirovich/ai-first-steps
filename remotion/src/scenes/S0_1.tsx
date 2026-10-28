import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Card, Title } from "../components/Card";
import type { SceneProps } from ".";
import { Cat } from "../components/Cat";
export const S0_1: React.FC<SceneProps> = () => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const typed = "нарисуй кота-космонавта на Луне".slice(0, Math.floor(f / 2.2));
  const reveal = interpolate(f, [fps * 2.2, fps * 4.2], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <>
      <Title>Первые шаги в ИИ</Title>
      <Card x={140} y={300} w={760} bg="#111c33" size={38}><span style={{ fontFamily: "monospace" }}>› {typed}{f % 20 < 10 ? "▌" : " "}</span></Card>
      <Cat style={{ position: "absolute", left: 960, top: 150, width: 520, opacity: reveal, filter: `blur(${(1 - reveal) * 24}px)`, borderRadius: 28 }} />
    </>
  );
};
