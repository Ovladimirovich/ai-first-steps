import { AbsoluteFill, Audio, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { PixarCard } from "../components/PixarCard";
import type { SceneProps } from ".";
import { P, PFONT } from "../pixarTheme";
import timingPixar from "../../public/timing-pixar.json";

/**
 * Персонажная сцена Remotion-ветки (превью того же кадра, что собирает
 * tools/pixar_frame.py для FFmpeg-тракта).
 *
 * Использует общие ассеты:
 *   remotion/public/pixar/bit.png, bit_happy.png, masha.png, masha_surprised.png
 *   remotion/public/pixar/scene_<scene>.jpg
 *
 * Заглушек нет: фон = сцена, «персонажи» = настоящие PNG с прозрачностью.
 */

type Who = "b" | "m";

const SPRITES: Record<string, string> = {
  b: "pixar/bit.png",
  b_happy: "pixar/bit_happy.png",
  m: "pixar/masha.png",
  m_surprised: "pixar/masha_surprised.png",
};

export const MyPixarScene: React.FC<SceneProps> = ({ lines, sceneStart, sceneId = "0.1" }) => {
  const f = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const t = f / fps;
  const d = (i: number) => Math.round(((lines[i]?.start ?? 0) - sceneStart) * fps);

  // активная реплика: та, что уже началась и ещё не кончилась
  const idx = lines.findIndex(
    (l) => t + sceneStart >= l.start && t + sceneStart <= l.end + 0.15
  );
  const active = idx >= 0 ? idx : lines.findIndex((l) => t + sceneStart < l.start) - 1;
  const line = lines[Math.max(0, active)] as (typeof lines)[number] | undefined;
  const who: Who = line?.who === "m" ? "m" : "b";

  // караоке: доля произнесённого внутри реплики
  const progress = line
    ? Math.max(0, Math.min(1, (t + sceneStart - line.start) / Math.max(0.1, line.end - line.start)))
    : 0;
  const words = (line?.text ?? "").split(" ");
  const lit = Math.round(words.length * progress);

  const scene = sceneId in TITLE ? sceneId : "0.1";
  const bg = `pixar/scene_${scene}.jpg`;

  const bob = (amp: number, period: number, phase: number) =>
    Math.sin((2 * Math.PI * t) / period + phase) * amp;

  const hero = (
    who_: Who,
    emotion: string,
    left: number,
    size: number,
    phase: number
  ) => {
    const isActive = who_ === who;
    const scale = isActive ? 1 : 0.9;
    return (
      <img
        key={who_}
        src={staticFile(SPRITES[isActive && emotion ? `${who_}_${emotion}` : who_] ?? SPRITES[who_])}
        alt={who_ === "b" ? "Бит" : "Маша"}
        style={{
          position: "absolute",
          bottom: 40 - (isActive ? 12 : 0),
          left,
          width: size * scale,
          height: size * scale,
          objectFit: "contain",
          opacity: isActive ? 1 : 0.68,
          filter: isActive
            ? `drop-shadow(0 0 42px ${who_ === "b" ? "rgba(46,230,214,.55)" : "rgba(255,107,107,.5)"}) drop-shadow(0 18px 30px rgba(0,0,0,.45))`
            : "drop-shadow(0 18px 30px rgba(0,0,0,.35)) saturate(.8)",
          transform: `translateY(${bob(who_ === "b" ? 9 : 4, who_ === "b" ? 2.6 : 3.4, phase)}px)`,
          transition: "none",
        }}
      />
    );
  };

  return (
    <div style={{ width, height, position: "relative", overflow: "hidden", background: "#0B1224" }}>
      {/* фон сцены: лёгкая панорама камерой */}
      <div
        style={{
          position: "absolute",
          inset: -40,
          background: `url(${staticFile(bg)}) center/cover no-repeat`,
          transform: `translateX(${interpolate(f, [0, 900], [0, -28], { extrapolateRight: "extend" })}px)`,
        }}
      />
      {/* затемнение снизу под карточку + верх под титул */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg, rgba(6,10,22,.55) 0%, rgba(6,10,22,0) 22%, rgba(6,10,22,0) 45%, rgba(6,10,22,.78) 100%)",
        }}
      />

      {/* титул сцены в пилюле */}
      <div
        style={{
          position: "absolute",
          top: 28,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            fontFamily: PFONT,
            fontWeight: 800,
            fontSize: 46,
            color: "#fff",
            background: "rgba(10,16,32,.55)",
            border: "1px solid rgba(255,255,255,.10)",
            borderRadius: 38,
            padding: "12px 30px",
            textShadow: "0 4px 18px rgba(0,0,0,.5)",
          }}
        >
          {TITLE[scene]}
        </div>
      </div>

      {/* персонажи: говорящий крупнее и с ореолом, слушающий приглушён */}
      {hero("b", who === "b" ? "happy" : "", 150, 620, 0)}
      {hero("m", who === "m" ? "surprised" : "", width - 150 - 620, 620, 1.7)}

      {/* карточка реплики с караоке */}
      {line && (
        <PixarCard x={(width - 1040) / 2} y={height - 300} w={1040} delay={d(Math.max(0, active))} size={40}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
            <span
              style={{
                background: who === "b" ? P.teal : P.coral,
                color: "#0C1424",
                fontWeight: 800,
                fontSize: 26,
                padding: "6px 18px",
                borderRadius: 22,
              }}
            >
              {who === "b" ? "БИТ" : "МАША"}
            </span>
          </div>
          {words.map((w, i) => (
            <span
              key={i}
              style={{
                color: i < lit ? P.yellow : "#F4F6FA",
                textShadow: i < lit ? "0 0 18px rgba(255,210,63,.55)" : "none",
              }}
            >
              {w + " "}
            </span>
          ))}
        </PixarCard>
      )}
    </div>
  );
};

const TITLE: Record<string, string> = {
  "0.1": "Гора домашки",
  "0.2": "4 суперсилы",
  "1.1": "Не понял на уроке?",
  "1.2": "Объясни как для друга",
  "1.3": "Тренер, а не костыль",
  "1.4": "Суперсила 1: Репетитор 24/7",
  "2.1": "Хочу, но не умею рисовать",
  "2.2": "Из шума — в картину",
  "2.3": "Твоя обложка, твой трек",
  "2.4": "Суперсила 2: Творец",
  "3.1": "Чек-вопрос",
  "4.1": "Генератор идей",
  "4.2": "Менеджер проекта",
  "4.3": "Будь детективом",
  "4.4": "Суперсила 3: Исследователь",
  "5.1": "Кем буду работать?",
  "5.2": "Архитектор миров",
  "5.3": "Портфолио сейчас",
  "5.4": "Суперсила 4: Будущее",
  "6.1": "Подвох: галлюцинации",
  "6.2": "3 правила",
  "6.3": "Как работает ИИ",
  "7.1": "ИИ сделает умнее?",
  "8.1": "4 причины дружить",
  "8.2": "Челлендж на неделю",
};

/**
 * Обёртка для самостоятельного рендера без SceneProps:
 * берёт реальные реплики сцены 0.1 из remotion/public/timing-pixar.json
 * (14 секунд), чтобы композиция MyPixar показывала настоящий кадр ролика.
 */
export const MyPixarStandalone: React.FC = () => {
  const sceneLines = (timingPixar.lines as any[])
    .filter((l) => l.scene === "0.1")
    .map((l) => ({ ...l, start: l.start - 0, end: l.end }))
    .slice(0, 3);
  return (
    <AbsoluteFill>
      {/* звук ролика: 57 реплик, два голоса */}
      <Audio src={staticFile("audio/voice_track-pixar.mp3")} />
      <MyPixarScene sceneId="0.1" lines={sceneLines as any} sceneStart={0} />
    </AbsoluteFill>
  );
};
