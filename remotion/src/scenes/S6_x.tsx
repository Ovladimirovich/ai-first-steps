import { interpolate, useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
const L = (lines: SceneProps["lines"], s: number, i: number, fr = 0) => Math.round(((lines[i]?.start ?? 0) + ((lines[i]?.end ?? 0) - (lines[i]?.start ?? 0)) * fr - s) * 30);

export const S5_4: React.FC<SceneProps> = () => (
  <>
    <Title>Запомним</Title>
    <Card x={100} y={300} w={1000} size={54}>Картинка: <HL>промпт</HL> → из шума, <HL>шаг за шагом</HL></Card>
  </>
);

// Маленький кот для киноленты; glitch — третья лапа и другой цвет
const MiniCat: React.FC<{ wave: number; glitch?: boolean; color?: string }> = ({ wave, glitch, color = "#f2a65a" }) => (
  <svg viewBox="0 0 100 100" width="150" height="150">
    <rect width="100" height="100" fill="#060a1a" /><ellipse cx="50" cy="95" rx="70" ry="18" fill="#8d8d9c" />
    <circle cx="50" cy="55" r="20" fill={glitch ? "#7ad17a" : color} />
    <polygon points="33,45 37,28 47,40" fill={glitch ? "#7ad17a" : color} /><polygon points="67,45 63,28 53,40" fill={glitch ? "#7ad17a" : color} />
    <circle cx="43" cy="53" r="2.5" /><circle cx="57" cy="53" r="2.5" />
    <rect x="30" y="72" width="40" height="20" rx="6" fill="#fff" />
    <rect x="72" y={60 - wave * 14} width="8" height="22" rx="4" fill={glitch ? "#7ad17a" : color} transform={`rotate(${-30 * wave} 76 82)`} />
    {glitch && <rect x="18" y="66" width="8" height="22" rx="4" fill="#7ad17a" transform="rotate(25 22 66)" />}
  </svg>
);

export const S6_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => L(lines, sceneStart, i, fr);
  const glitchOn = f > d(1, 0.55) && f < d(3, 0.4);
  const frames = 6;
  return (
    <>
      <Title>Видео = много картинок подряд</Title>
      <div style={{ position: "absolute", left: 80, top: 230, width: 1040, height: 220, background: "#111", borderRadius: 16, borderTop: "22px dashed #444", borderBottom: "22px dashed #444", display: "flex", gap: 14, padding: "12px 20px", overflow: "hidden" }}>
        {Array.from({ length: frames }).map((_, i) => {
          const idx = Math.floor(f / 4) + i; const wave = (Math.sin(idx * 0.6) + 1) / 2;
          const glitch = glitchOn && (idx % 7 === 3 || idx % 11 === 5);
          return <div key={i} style={{ outline: glitch ? "5px solid #FF6B6B" : "none", borderRadius: 8 }}><MiniCat wave={wave} glitch={glitch} /></div>;
        })}
      </div>
      <Card x={80} y={490} w={1040} size={34} delay={d(1, 0.1)}>24 кадра в секунду. Кадры должны <HL>дружить</HL>: без смены цвета и третьей лапы</Card>
      {f > d(3, 0.4) && <Card x={80} y={650} w={1040} size={34} delay={d(3, 0.4)} bg="#3a2a4a">Сейчас модель следит за кадром <HL>и за временем</HL>. Kandinsky Video — ролики со звуком</Card>}
    </>
  );
};

const notes = ["до", "ре", "ми", "фа", "соль", "ля", "си", "до"];
export const S6_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => L(lines, sceneStart, i, fr);
  const shown = Math.min(notes.length, Math.max(3, Math.floor((f - d(0, 0.4)) / 14) + 3));
  const guessing = f > d(0, 0.4) && shown < notes.length;
  return (
    <>
      <Title>Музыка — сестра текста</Title>
      <Card x={80} y={220} w={1040} size={40}>
        <div style={{ display: "flex", gap: 14, alignItems: "flex-end", height: 160 }}>
          {notes.slice(0, shown).map((n, i) => (
            <div key={i} style={{ width: 110, height: 60 + i * 12, background: i === shown - 1 && guessing ? "#FFD23F" : "#2EE6D6", borderRadius: 12, color: "#0d1526", fontWeight: 800, display: "grid", placeItems: "center" }}>{n}</div>
          ))}
          {guessing && <div style={{ width: 110, height: 60 + shown * 12, border: "4px dashed #FFD23F", borderRadius: 12, display: "grid", placeItems: "center", color: "#FFD23F" }}>?</div>}
        </div>
      </Card>
      <Card x={80} y={480} w={1040} size={34} delay={d(0, 0.5)}>«Угадай следующее слово» → <HL>«угадай следующую ноту»</HL> (или кусочек звука)</Card>
      {f > d(2) && <Card x={80} y={640} w={1040} size={34} delay={d(2)} bg="#3a2a4a">«Весёлая песня про лето, в стиле рок» → звук <HL>кусочек за кусочком</HL> + голос + слова</Card>}
      <svg viewBox="0 0 1040 80" style={{ position: "absolute", left: 80, top: 830, width: 1040, opacity: f > d(2) ? 1 : 0 }}>
        <path d={Array.from({ length: 105 }, (_, i) => `${i === 0 ? "M" : "L"}${i * 10} ${40 + Math.sin(i * 0.5 + f * 0.3) * 20 * Math.sin(i * 0.11 + f * 0.05)}`).join(" ")} stroke="#2EE6D6" strokeWidth="4" fill="none" />
      </svg>
    </>
  );
};

export const S6_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => L(lines, sceneStart, i, fr);
  const items = [["📝", "текст"], ["🖼", "картинки"], ["🎬", "видео"], ["🎵", "музыка"]];
  const pull = interpolate(f, [d(0, 0.5), d(0, 0.9)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <>
      <Title>Везде один принцип</Title>
      {items.map(([ic, t], i) => {
        const ang = (i / 4) * Math.PI * 2 - Math.PI / 2, r = 330 - pull * 40;
        return <div key={t} style={{ position: "absolute", left: 600 + Math.cos(ang) * r * 1.5 - 90, top: 480 + Math.sin(ang) * r * 0.8 - 60, width: 180, height: 120, background: "#243A66", borderRadius: 20, display: "grid", placeItems: "center", fontSize: 30, fontFamily: "Montserrat, Arial" }}><div>{ic}</div>{t}</div>;
      })}
      <div style={{ position: "absolute", left: 430, top: 410, width: 340, height: 140, borderRadius: 24, background: "#FFD23F", color: "#0d1526", display: "grid", placeItems: "center", textAlign: "center", fontSize: 26, fontWeight: 800, fontFamily: "Montserrat, Arial", opacity: pull }}>выучи на примерах →<br />достраивай по кусочкам</div>
      {lines[2] && f > d(2) && <Card x={80} y={740} w={1040} size={32} delay={d(2)} bg="#3a2a4a">Идея простая. Сложно — заставить работать <HL>миллиарды ручек</HL></Card>}
    </>
  );
};
