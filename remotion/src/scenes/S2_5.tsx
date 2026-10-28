import { Card, HL, Title } from "../components/Card";
import type { SceneProps } from ".";
export const S2_5: React.FC<SceneProps> = () => (
  <>
    <Title>Запомним</Title>
    <Card x={140} y={260} w={960} size={50}><b>Модель</b> = <HL>миллиарды настроек</HL>, подобранных на примерах</Card>
    <Card x={140} y={520} w={960} size={50} delay={60}><b>Языковая модель</b> угадывает <HL>следующее слово</HL></Card>
  </>
);
