import { interpolate, useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import { Cat } from "../components/Cat";
import type { SceneProps } from ".";
const credits = [
  "Факты о сервисах актуальны на 27 октября 2026",
  "Сценарий, анимация, озвучка: проект «Первые шаги в ИИ»",
  "Инструменты: Remotion · нейросетевой TTS · ffmpeg · Python",
  "Названия ChatGPT, Алиса, GigaChat, Kandinsky — товарные знаки их владельцев, упомянуты в образовательных целях",
  "Персонажи, иконки и фон — авторские SVG · Лицензия материалов: CC BY-NC 4.0",
];
export const S8_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  const end = Math.round(((lines[lines.length - 1]?.end ?? 0) - sceneStart) * 30);
  const dogX = interpolate(f, [d(1), d(1) + 90], [-200, 1300], { extrapolateRight: "clamp" });
  const credO = interpolate(f, [end + 20, end + 50], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <>
      <Title>Попробуй сам</Title>
      <Card x={100} y={200} w={1000} size={36} delay={d(0)}>Задай боту вопрос, ответ на который <HL>точно знаешь</HL> — и проверь, не придумал ли он</Card>
      {f > d(1) && <Cat style={{ position: "absolute", left: 100, top: 400, width: 300, height: 300, borderRadius: 24, opacity: interpolate(f, [d(2), d(2) + 40], [0.3, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }} />}
      {f > d(2) && <Card x={440} y={480} w={660} size={34} delay={d(2)} bg="#3a2a4a">Нарисуй ещё одного — <HL>теперь ты знаешь, как</HL></Card>}
      {/* Пёс Пиксель пробегает */}
      <svg viewBox="0 0 120 80" style={{ position: "absolute", left: dogX, top: 780, width: 180 }}>
        <ellipse cx="60" cy="50" rx="40" ry="22" fill="#c98b4a" /><circle cx="100" cy="40" r="18" fill="#c98b4a" /><ellipse cx="88" cy="30" rx="7" ry="14" fill="#8b5a2b" />
        <circle cx="106" cy="38" r="3" /><rect x="30" y="60" width="10" height="18" rx="4" fill="#8b5a2b" transform={`rotate(${Math.sin(f) * 25} 35 60)`} /><rect x="75" y="60" width="10" height="18" rx="4" fill="#8b5a2b" transform={`rotate(${-Math.sin(f) * 25} 80 60)`} />
        <path d="M20 45 q-15 -20 -5 -30" stroke="#c98b4a" strokeWidth="8" fill="none" strokeLinecap="round" />
      </svg>
      {/* Титры */}
      <div style={{ position: "absolute", inset: 0, background: "#1B2A4A", opacity: credO }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 120, textAlign: "center", fontFamily: "Montserrat, Arial", fontWeight: 800, fontSize: 72, color: "#2EE6D6" }}>Первые шаги в ИИ</div>
        {credits.map((c, i) => <div key={i} style={{ position: "absolute", left: 200, right: 200, top: 300 + i * 110, textAlign: "center", fontFamily: "Montserrat, Arial", fontSize: 30, lineHeight: 1.4, color: "#F4F6FA", opacity: interpolate(f, [end + 40 + i * 12, end + 60 + i * 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{c}</div>)}
      </div>
    </>
  );
};
