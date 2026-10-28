import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
const L = (lines: SceneProps["lines"], s: number, i: number, fr = 0) => Math.round(((lines[i]?.start ?? 0) + ((lines[i]?.end ?? 0) - (lines[i]?.start ?? 0)) * fr - s) * 30);

export const S7_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const q = lines[0], a = lines[1];
  const t0 = (q.end - sceneStart) * 30, t1 = a ? (a.start - sceneStart) * 30 : t0 + 135;
  const left = Math.max(0, Math.ceil(interpolate(f, [t0, t1], [5, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })));
  const revealed = f >= t1;
  return (
    <>
      <Title>⏱ Проверка №2</Title>
      <Card x={140} y={220} w={960} size={60}>ИИ всегда прав?</Card>
      <div style={{ position: "absolute", left: 140, top: 420, display: "flex", gap: 40 }}>
        {["ДА", "НЕТ"].map((o) => (
          <div key={o} style={{ width: 300, height: 140, borderRadius: 28, display: "grid", placeItems: "center", fontSize: 64, fontWeight: 800, fontFamily: "Montserrat, Arial", background: revealed && o === "НЕТ" ? "#2EE6D6" : "#243A66", color: revealed && o === "НЕТ" ? "#0d1526" : "#fff", transform: revealed && o === "НЕТ" ? "scale(1.08)" : "none" }}>{o}</div>
        ))}
        {!revealed && f > t0 && <div style={{ width: 140, height: 140, borderRadius: 70, border: "10px solid #FFD23F", display: "grid", placeItems: "center", fontSize: 70, fontWeight: 800, color: "#FFD23F" }}>{left}</div>}
      </div>
      {revealed && <Card x={140} y={640} w={960} delay={t1} bg="#3a2a4a">Нет! И вот <HL>почему</HL>…</Card>}
    </>
  );
};

const Shield: React.FC<{ x: number; delay: number; color: string; icon: React.ReactNode; title: string; sub: string }> = ({ x, delay, color, icon, title, sub }) => {
  const { fps } = useVideoConfig(); const s = spring({ frame: useCurrentFrame() - delay, fps, config: { damping: 11, stiffness: 110 } });
  return (
    <div style={{ position: "absolute", left: x, top: 200, width: 330, opacity: s, transform: `scale(${0.6 + 0.4 * s})`, fontFamily: "Montserrat, Arial", textAlign: "center" }}>
      <svg viewBox="0 0 120 140" width="330" height="330"><path d="M60 6 L110 24 V70 C110 105 85 125 60 134 C35 125 10 105 10 70 V24 Z" fill={color} />
        <foreignObject x="10" y="20" width="100" height="100"><div style={{ width: 100, height: 100, display: "grid", placeItems: "center" }}>{icon}</div></foreignObject></svg>
      <div style={{ fontSize: 36, fontWeight: 800, marginTop: 4 }}>{title}</div>
      <div style={{ fontSize: 24, opacity: 0.85, marginTop: 6 }}>{sub}</div>
    </div>
  );
};
export const S7_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => L(lines, sceneStart, i, fr);
  const glass = <svg viewBox="0 0 60 60" width="70" height="70"><circle cx="26" cy="26" r="16" stroke="#fff" strokeWidth="6" fill="none" /><line x1="38" y1="38" x2="54" y2="54" stroke="#fff" strokeWidth="7" strokeLinecap="round" /></svg>;
  const pen = <svg viewBox="0 0 60 60" width="70" height="70"><path d="M10 50 L14 38 L40 12 L48 20 L22 46 Z" fill="#fff" /><line x1="8" y1="54" x2="52" y2="54" stroke="#fff" strokeWidth="5" /></svg>;
  const lock = <svg viewBox="0 0 60 60" width="70" height="70"><rect x="12" y="26" width="36" height="28" rx="6" fill="#fff" /><path d="M20 26 V18 a10 10 0 0 1 20 0 V26" stroke="#fff" strokeWidth="6" fill="none" /></svg>;
  return (
    <>
      <Title>Три правила</Title>
      <Shield x={90} delay={d(0, 0.05)} color="#2EE6D6" icon={glass} title="Проверяй" sub="ИИ угадывает — бывают «галлюцинации»" />
      <Shield x={440} delay={d(1, 0.05)} color="#FFD23F" icon={pen} title="Не выдавай за своё" sub="помощник, а не автор" />
      <Shield x={790} delay={d(2, 0.05)} color="#FF6B6B" icon={lock} title="Не вводи личное" sub="пароли, адрес, документы" />
      {f > d(0, 0.5) && f < d(1) && <Card x={90} y={720} w={1030} size={32} delay={d(0, 0.5)} bg="#3a2a4a">Уверенная выдумка = <HL>галлюцинация</HL></Card>}
      {f > d(2, 0.6) && f < d(4) && <Card x={90} y={720} w={1030} size={32} delay={d(2, 0.6)} bg="#3a2a4a">Это сервис компании: написанное <HL>может сохраниться</HL></Card>}
      {f > d(4) && <Card x={90} y={720} w={1030} size={32} delay={d(4)} bg="#3a2a4a">Спросить — можно. Потом <HL>реши сама и сравни</HL></Card>}
    </>
  );
};

export const S8_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => L(lines, sceneStart, i, fr);
  const items = [
    ["1", "ИИ учится на примерах", 0.08],
    ["2", "Модель — миллиарды настроек; языковая угадывает следующее слово", 0.3],
    ["3", "ChatGPT, Алиса AI, GigaChat — разные марки, один мотор", 0.58],
    ["4", "Картинки, видео, музыка — из шума и по кусочкам", 0.8],
  ] as const;
  return (
    <>
      <Title>Повторим за десять секунд</Title>
      {items.map(([n, t, fr], i) => (
        <Card key={n} x={90} y={190 + i * 150} w={1030} size={32} delay={d(0, fr)}><span style={{ color: "#FFD23F", fontWeight: 800, marginRight: 18 }}>{n}</span>{t}</Card>
      ))}
      {lines[1] && f > d(1) && <Card x={90} y={800} w={1030} size={30} delay={d(1)} bg="#3a2a4a">…и половину <HL>объяснила сама</HL> 🙂</Card>}
    </>
  );
};
