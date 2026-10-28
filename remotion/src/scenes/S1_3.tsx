import { interpolate, useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
const pets = "cdccdcddcdcd".split("");
const Pet: React.FC<{ k: string }> = ({ k }) => k === "c" ? (
  <svg viewBox="0 0 60 60" width="84" height="84"><polygon points="10,30 12,6 28,20" fill="#f2a65a"/><polygon points="50,30 48,6 32,20" fill="#f2a65a"/><circle cx="30" cy="34" r="22" fill="#f2a65a"/><circle cx="22" cy="32" r="3"/><circle cx="38" cy="32" r="3"/><path d="M25 42 q5 5 10 0" stroke="#000" strokeWidth="2" fill="none"/></svg>
) : (
  <svg viewBox="0 0 60 60" width="84" height="84"><ellipse cx="10" cy="30" rx="8" ry="16" fill="#8b5a2b"/><ellipse cx="50" cy="30" rx="8" ry="16" fill="#8b5a2b"/><circle cx="30" cy="34" r="22" fill="#c98b4a"/><circle cx="22" cy="30" r="3"/><circle cx="38" cy="30" r="3"/><ellipse cx="30" cy="42" rx="6" ry="4"/></svg>
);
export const S1_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  const n = Math.round(10 * Math.pow(1000, interpolate(f, [20, 200], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })));
  const shown = Math.min(pets.length, Math.floor(f / 8));
  return (
    <>
      <Title>Учимся на примерах</Title>
      <Card x={140} y={200} w={760} size={96} delay={d(0)}>
        <div style={{ textAlign: "center", color: "#2EE6D6", fontWeight: 800 }}>{n.toLocaleString("ru")}</div>
        <div style={{ textAlign: "center", fontSize: 34 }}>фотографий с подписями</div>
      </Card>
      <Card x={140} y={470} w={760} size={70} delay={d(0)}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "center" }}>{pets.slice(0, shown).map((k, i) => <Pet key={i} k={k} />)}</div>
      </Card>
      <Card x={140} y={690} w={760} delay={d(2)}>ИИ — программа, которая <HL>учится на примерах</HL></Card>
    </>
  );
};
