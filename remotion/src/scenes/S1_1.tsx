import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
export const S1_1: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const d = (i: number) => Math.round((lines[i].start - sceneStart) * 30);
  return (
    <>
      <Title>Обычная программа — это рецепт</Title>
      <Card x={140} y={240} w={760} delay={d(0)}><b style={{ color: "#FFD23F" }}>📖 Рецепт</b><br />1. Взять яйцо<br />2. Разбить<br />3. Жарить 3 минуты</Card>
      <Card x={140} y={640} w={760} delay={d(2)} bg="#3a2a4a">🧮 2 + 2 = 4. <HL>Всегда.</HL></Card>
    </>
  );
};
