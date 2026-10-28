import { Title, Card } from "../components/Card";
import type { SceneProps } from ".";
export const Placeholder: React.FC<SceneProps> = ({ sceneId }) => (
  <>
    <Title>Сцена {sceneId} — в работе</Title>
    <Card x={120} y={220} w={900}>Анимация этой сцены будет добавлена после озвучки блока.</Card>
  </>
);
