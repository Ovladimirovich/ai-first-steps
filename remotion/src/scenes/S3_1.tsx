import { interpolate, useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
export const S3_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  const q = lines[0], a = lines[1];
  const t0 = (q.end - sceneStart) * 30, t1 = (a.start - sceneStart) * 30;
  const left = Math.max(0, Math.ceil(interpolate(f, [t0, t1], [5, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })));
  const revealed = f >= t1;
  return (
    <>
      <Title>⏱ Проверка №1</Title>
      <Card x={140} y={220} w={960} size={60}>Калькулятор — это ИИ?</Card>
      <div style={{ position: "absolute", left: 140, top: 420, display: "flex", gap: 40 }}>
        {["ДА", "НЕТ"].map((o) => (
          <div key={o} style={{ width: 300, height: 140, borderRadius: 28, display: "grid", placeItems: "center", fontSize: 64, fontWeight: 800, fontFamily: "Montserrat, Arial", background: revealed ? (o === "НЕТ" ? "#2EE6D6" : "#243A66") : "#243A66", color: revealed && o === "НЕТ" ? "#0d1526" : "#fff", transform: revealed && o === "НЕТ" ? "scale(1.08)" : "none" }}>{o}</div>
        ))}
        {!revealed && f > t0 && <div style={{ width: 140, height: 140, borderRadius: 70, border: "10px solid #FFD23F", display: "grid", placeItems: "center", fontSize: 70, fontWeight: 800, color: "#FFD23F" }}>{left}</div>}
      </div>
      {revealed && <Card x={140} y={640} w={960} delay={t1} bg="#3a2a4a">Работает по рецепту, <HL>ничему не учится</HL> → не ИИ</Card>}
    </>
  );
};
