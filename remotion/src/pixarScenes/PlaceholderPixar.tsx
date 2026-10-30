import { PixarCard, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PlaceholderPixar: React.FC<SceneProps> = ({ sceneId, lines, sceneStart }) => {
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);
  return (
    <>
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)" }} />
      <PixarTitle light>Сцена {sceneId} · Pixar</PixarTitle>
      <PixarCard x={90} y={220} w={1740} delay={d(0)} bg="#243A66" size={30}>
        {lines[0]?.text ?? "Pixar-сцена в работе — подставь озвучку и фон из assets/pixar/"}
      </PixarCard>
      {lines[1] && <PixarCard x={90} y={420} w={1740} delay={d(1)} bg="#fff" size={28}><span style={{ color: "#1B2A4A" }}>{lines[1].text}</span></PixarCard>}
      {lines[2] && <PixarCard x={90} y={620} w={1740} delay={d(2)} bg="#1f5e46" size={26}>{lines[2].text}</PixarCard>}
    </>
  );
};
