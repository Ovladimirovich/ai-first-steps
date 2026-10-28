import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
const guesses = ["усы", "хвост", "«мяу»"];
export const S1_2: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  return (
    <>
      <Title>Научи компьютер отличать кошку от собаки</Title>
      <Card x={140} y={220} w={760} size={64} delay={d(0)}>Кошка или собака? ❓</Card>
      {guesses.map((g, i) => (
        <Card key={g} x={140} y={420 + i * 130} w={760} delay={d(1 + i * 2)}>{g} → <HL>у собак тоже</HL></Card>
      ))}
    </>
  );
};
