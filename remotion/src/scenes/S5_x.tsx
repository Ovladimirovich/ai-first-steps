import { interpolate, useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import { Cat } from "../components/Cat";
import type { SceneProps } from ".";
const L = (lines: SceneProps["lines"], s: number, i: number, fr = 0) => Math.round(((lines[i]?.start ?? 0) + ((lines[i]?.end ?? 0) - (lines[i]?.start ?? 0)) * fr - s) * 30);

export const S5_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => L(lines, sceneStart, i, fr);
  return (
    <>
      <Title>А картинки?</Title>
      <Card x={100} y={220} w={1000} bg="#111c33" delay={d(1, 0.2)}><span style={{ fontFamily: "monospace", fontSize: 36 }}>› кот-космонавт на Луне</span></Card>
      {f > d(1, 0.3) && <Card x={100} y={380} w={1000} delay={d(1, 0.3)}>Это <HL>промпт</HL> — заказ художнику</Card>}
      {f > d(1, 0.75) && <Card x={100} y={560} w={1000} delay={d(1, 0.75)} bg="#3a2a4a">А рисует модель вот как… 🎨</Card>}
    </>
  );
};

// Диффузия: кот под слоем SVG-шума; seed шума меняется каждый кадр, непрозрачность и размытие падают к концу реплики.
export const S5_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => L(lines, sceneStart, i, fr);
  const p = interpolate(f, [d(0, 0.15), d(0, 0.95)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const step = Math.round(1 + 49 * p), ease = p * p;
  return (
    <>
      <Title>Из шума — шаг за шагом</Title>
      <div style={{ position: "absolute", left: 100, top: 200, width: 560, height: 560, borderRadius: 28, overflow: "hidden", background: "#000" }}>
        <Cat style={{ width: 560, height: 560, filter: `blur(${(1 - ease) * 18}px) saturate(${0.3 + 0.7 * ease})`, display: "block" }} />
        <svg width="560" height="560" style={{ position: "absolute", left: 0, top: 0, opacity: 1 - ease, mixBlendMode: "normal" }}>
          <filter id="nz"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed={f % 97} stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /><feComponentTransfer><feFuncA type="linear" slope="1" /></feComponentTransfer></filter>
          <rect width="560" height="560" filter="url(#nz)" />
        </svg>
      </div>
      <Card x={700} y={200} w={420} size={34}>Шаг <b style={{ color: "#FFD23F", fontSize: 54 }}>{step}</b> / 50
        <div style={{ height: 14, background: "#1B2A4A", borderRadius: 7, marginTop: 12 }}><div style={{ height: "100%", width: `${p * 100}%`, background: "#2EE6D6", borderRadius: 7 }} /></div>
      </Card>
      <Card x={700} y={400} w={420} size={30}>«На что это похоже, если тут должен быть <HL>кот-космонавт</HL>?»</Card>
      {f > d(1) && <Card x={700} y={600} w={420} size={30} delay={d(1)} bg="#3a2a4a">Как фотография проявляется — только её <HL>не существовало</HL></Card>}
    </>
  );
};

export const S5_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => L(lines, sceneStart, i, fr);
  const pairs = ["кот", "Луна", "ракета", "собака", "пирамида", "море", "кот в шляпе", "скафандр"];
  const egypt = f > d(1, 0.5);
  return (
    <>
      <Title>Откуда она знает, как выглядит кот?</Title>
      <div style={{ position: "absolute", left: 100, top: 200, width: 1000, height: 150, overflow: "hidden", borderRadius: 24, background: "#243A66" }}>
        {pairs.concat(pairs).map((w, i) => (
          <div key={i} style={{ position: "absolute", left: ((i * 260 - f * 3) % (pairs.length * 260) + pairs.length * 260) % (pairs.length * 260) - 260, top: 20, width: 230, height: 110, background: "#1B2A4A", borderRadius: 16, display: "grid", placeItems: "center", fontSize: 26 }}>
            <div style={{ width: 60, height: 40, background: "#2EE6D6", borderRadius: 6, opacity: .5 }} />«{w}»
          </div>
        ))}
      </div>
      <Card x={100} y={390} w={1000} delay={d(0, 0.4)}>Миллионы картинок <HL>с подписями</HL> → слова связались с тем, как это выглядит</Card>
      {f > d(1) && <Cat egypt={egypt} style={{ position: "absolute", left: 100, top: 560, width: 300, height: 300, borderRadius: 24 }} />}
      {f > d(1) && <Card x={440} y={620} w={660} delay={d(1)} bg="#3a2a4a">«кот в стиле древнего Египта» = <HL>кот</HL> + <HL>Египет</HL> из губки</Card>}
    </>
  );
};
