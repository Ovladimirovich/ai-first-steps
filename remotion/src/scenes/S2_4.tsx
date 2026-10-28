import { useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
const words = "Небо голубое, потому что воздух рассеивает синий свет сильнее остальных".split(" ");
export const S2_4: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  const shown = Math.max(0, Math.floor((f - d(0) - 10) / 9));
  return (
    <>
      <Title>Из слов — в ответ</Title>
      <Card x={140} y={200} w={900} bg="#111c33"><span style={{ fontFamily: "monospace", fontSize: 36 }}>› Почему небо голубое?</span></Card>
      <Card x={140} y={340} w={900} delay={d(0)}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
          {words.slice(0, shown).map((w, i) => <span key={i} style={{ background: "#1B2A4A", borderRadius: 10, padding: "4px 14px", border: `3px solid ${i === shown - 1 ? "#FFD23F" : "#2EE6D6"}` }}>{w}</span>)}
          {shown < words.length && f > d(0) && <span style={{ color: "#FFD23F" }}>▌</span>}
        </div>
      </Card>
      {f > d(1) && <Card x={140} y={640} w={900} delay={d(1)} bg="#3a2a4a">Она не знает — она <HL>очень хорошо угадывает</HL></Card>}
    </>
  );
};
