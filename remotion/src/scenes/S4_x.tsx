import { useCurrentFrame } from "remotion";
import { Card, HL, Title } from "../components/Card";
import { BotCard } from "../components/BotCard";
import type { SceneProps } from ".";
const lineAt = (lines: SceneProps["lines"], start: number, i: number, frac = 0) => Math.round(((lines[i].start + (lines[i].end - lines[i].start) * frac) - start) * 30);

export const S4_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => lineAt(lines, sceneStart, i, fr);
  return (
    <>
      <Title>Чем они отличаются?</Title>
      <BotCard bot="chatgpt" x={100} y={200} w={330} h={300} delay={d(0, 0.3)} />
      <BotCard bot="alice" x={460} y={200} w={330} h={300} delay={d(0, 0.5)} />
      <BotCard bot="giga" x={820} y={200} w={330} h={300} delay={d(0, 0.7)} />
      {f > d(1) && <Card x={100} y={560} w={960} delay={d(1)}>Внутри у всех — <HL>языковая модель</HL>. Разные компании, разные тексты, разные «руки и ноги».</Card>}
    </>
  );
};
export const S4_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => lineAt(lines, sceneStart, i, fr);
  return (
    <>
      <Title>ChatGPT</Title>
      <BotCard bot="chatgpt" big x={100} y={190} w={980} facts={[
        { t: "🚀 с него в конце 2022 началась мода на ИИ", at: d(0, 0.2) },
        { t: "🌍 десятки языков, лучше всего — английский", at: d(0, 0.5) },
        { t: "🧠 внутри — шестое поколение, GPT-6", at: d(0, 0.8) },
      ]} />
      {f > d(2) && <Card x={100} y={720} w={980} delay={d(2)} bg="#3a2a4a">🚫 В России официально <HL>не работает</HL></Card>}
    </>
  );
};
export const S4_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const d = (i: number, fr = 0) => lineAt(lines, sceneStart, i, fr);
  return (
    <>
      <Title>Алиса AI</Title>
      <BotCard bot="alice" big x={100} y={190} w={980} facts={[
        { t: "🔊 2017: голосовой помощник — музыка, погода, будильник", at: d(0, 0.1) },
        { t: "🧠 потом — большая языковая модель: тексты, картинки, разбор фото", at: d(0, 0.35) },
        { t: "📱 везде: колонка, телефон, браузер, машина", at: d(0, 0.6) },
        { t: "🚕 не только отвечает — делает: такси, продукты", at: d(0, 0.8) },
      ]} />
    </>
  );
};
export const S4_4: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame(); const d = (i: number, fr = 0) => lineAt(lines, sceneStart, i, fr);
  return (
    <>
      <Title>GigaChat</Title>
      <BotCard bot="giga" big x={100} y={190} w={980} facts={[
        { t: "📚 учили на большом количестве русских текстов", at: d(0, 0.15) },
        { t: "🎨 внутри — Kandinsky: картинки и короткие видео со звуком", at: d(0, 0.5) },
        { t: "🆓 бесплатно и без лимитов", at: d(0, 0.85) },
      ]} />
      {f > d(1) && <Card x={100} y={720} w={980} delay={d(1)} bg="#3a2a4a">Kandinsky — <HL>художник внутри</HL> GigaChat</Card>}
    </>
  );
};
