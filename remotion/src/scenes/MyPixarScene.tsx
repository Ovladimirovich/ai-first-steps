import { interpolate, useCurrentFrame, useVideoConfig, staticFile } from "remotion";
import { PixarCard, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from ".";

/**
 * Сцена для Pixar Why AI с фоном pixar-style-preview.jpg.
 * Может использоваться как самостоятельный ролик или в составе PixarMain.
 */
export const MyPixarScene: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * 30);

  return (
    <div style={{ width, height, position: "relative", overflow: "hidden" }}>
      {/* Фон: pixar-style-preview.jpg (мастерская) */}
      <div style={{
        position: "absolute",
        inset: 0,
        background: `url(${staticFile("pixar/pixar-style-preview.jpg")}) center/cover no-repeat`,
      }} />

      {/* Легкая панорама фона (камера медленно движется) */}
      <div style={{
        position: "absolute",
        inset: 0,
        background: `url(${staticFile("pixar/pixar-style-preview.jpg")}) center/cover no-repeat`,
        transform: `translateX(${interpolate(f, [0, 900], [0, -40], { extrapolateRight: "clamp" })}px)`,
        opacity: 0.15,
        pointerEvents: "none",
      }} />

      {/* Заголовок сцены */}
      <PixarTitle light>Почему ИИ?</PixarTitle>

      {/* Карточка с репликой (появляется с пружинкой) */}
      {lines.length > 0 && f > d(0) && (
        <PixarCard x={120} y={620} w={1100} delay={d(0)} size={36}>
          {lines[0]?.text ?? "Привет, это моя анимация на базе Pixar Why AI."}
        </PixarCard>
      )}

      {/* Заглушка под персонажей — здесь можно вставить своих héros в PNG с прозрачностью */}
      <div style={{
        position: "absolute",
        bottom: 120,
        left: 500,
        width: 700,
        height: 350,
        display: "flex",
        gap: 40,
        justifyContent: "center",
        width: 700, height: 350, display: "flex", gap: 40, justifyContent: "center"
      }}>
        {/* Персонаж 1 (замените src на свой PNG) */}
        <img
          src={staticFile("pixar/pixar-style-preview.jpg")}
          alt="Персонаж 1"
          style={{
            width: 320, height: 320, objectFit: "contain",
            filter: "drop-shadow(0 20px 40px rgba(0,0,0,.35))",
            animation: "float 3s ease-in-out infinite"
          }}
        />
        {/* Персонаж 2 (замените src на свой PNG) */}
        <img
          src={staticFile("pixar/pixar-style-preview.jpg")}
          alt="Персонаж 2"
          style={{
            width: 280, height: 280, objectFit: "contain",
            filter: "drop-shadow(0 20px 40px rgba(0,0,0,.35))",
            animation: "float 3s ease-in-out infinite 1.5s"
          }}
        />
      </div>

      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-16px); }
        }
      `}</style>
    </div>
  );
};

/**
 * Обёртка для самостоятельного рендера без SceneProps.
 * Подставляет заглушечные реплики, чтобы сцена показалась живой.
 */
export const MyPixarStandalone: React.FC = () => {
  const mockLines = [
    { text: "Привет! Это мой новый ролик на базе Pixar Why AI.", start: 1 },
    { text: "Персонажи и фон — мои собственные.", start: 4 },
    { text: "Сделано с помощью Remotion.", start: 7 },
  ] as any;
  return <MyPixarScene lines={mockLines} sceneStart={0} />;
};