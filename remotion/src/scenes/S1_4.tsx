import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
export const S1_4: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  return (
    <>
      <Title>Запомним</Title>
      <Card x={140} y={300} w={900} size={56} delay={d(0)}>
        <b>ИИ</b> — программа, которая <HL>учится</HL> на примерах,<br />а не по готовому рецепту
      </Card>
      <Card x={140} y={640} w={620} size={46} delay={d(2)} bg="#3a2a4a">Хранит всё в… <HL>модели</HL></Card>
    </>
  );
};
