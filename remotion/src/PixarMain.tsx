import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import timing from "../public/timing-pixar.json";
import { Subtitles } from "./components/Subtitles";
import { PixarCharacters } from "./components/PixarCharacters";
import { PS0_1 } from "./pixarScenes/PS0_1";
import { PS0_2 } from "./pixarScenes/PS0_2";
import { PS1_1 } from "./pixarScenes/PS1_1";
import { PS1_2 } from "./pixarScenes/PS1_2";
import { PS1_3 } from "./pixarScenes/PS1_3";
import { PS1_4 } from "./pixarScenes/PS1_4";
import { PS2_1 } from "./pixarScenes/PS2_1";
import { PS2_2 } from "./pixarScenes/PS2_2";
import { PS2_3 } from "./pixarScenes/PS2_3";
import { PS2_4 } from "./pixarScenes/PS2_4";
import { PS3_1 } from "./pixarScenes/PS3_1";
import { PS4_1 } from "./pixarScenes/PS4_1";
import { PS4_2 } from "./pixarScenes/PS4_2";
import { PS4_3 } from "./pixarScenes/PS4_3";
import { PS4_4 } from "./pixarScenes/PS4_4";
import { PS5_1 } from "./pixarScenes/PS5_1";
import { PS5_2 } from "./pixarScenes/PS5_2";
import { PS5_3 } from "./pixarScenes/PS5_3";
import { PS5_4 } from "./pixarScenes/PS5_4";
import { PS6_1 } from "./pixarScenes/PS6_1";
import { PS6_2 } from "./pixarScenes/PS6_2";
import { PS6_3 } from "./pixarScenes/PS6_3";
import { PS7_1 } from "./pixarScenes/PS7_1";
import { PS8_1 } from "./pixarScenes/PS8_1";
import { PS8_2 } from "./pixarScenes/PS8_2";
import { PlaceholderPixar } from "./pixarScenes/PlaceholderPixar";
import type { SceneProps } from "./scenes";

export type PixarLine = (typeof timing.lines)[number];

const PIXAR_SCENES: Record<string, React.FC<SceneProps>> = {
  "0.1": PS0_1, "0.2": PS0_2,
  "1.1": PS1_1, "1.2": PS1_2, "1.3": PS1_3, "1.4": PS1_4,
  "2.1": PS2_1, "2.2": PS2_2, "2.3": PS2_3, "2.4": PS2_4,
  "3.1": PS3_1,
  "4.1": PS4_1, "4.2": PS4_2, "4.3": PS4_3, "4.4": PS4_4,
  "5.1": PS5_1, "5.2": PS5_2, "5.3": PS5_3, "5.4": PS5_4,
  "6.1": PS6_1, "6.2": PS6_2, "6.3": PS6_3,
  "7.1": PS7_1,
  "8.1": PS8_1, "8.2": PS8_2,
  "_placeholder": PlaceholderPixar,
};

export const sceneRangesPixar = () => {
  const ids = [...new Set(timing.lines.map((l) => l.scene))] as string[];
  return ids.map((id, i) => {
    const mine = timing.lines.filter((l) => l.scene === id);
    const next = timing.lines.find((l) => l.scene === ids[i + 1]);
    const start = Math.max(0, mine[0].start - 0.6);
    const end = next ? Math.max(0, next.start - 0.6) : timing.total + 6;
    return { id, start, end, lines: mine as unknown as SceneProps["lines"] };
  });
};

export const PixarMain: React.FC<{ subs?: boolean }> = ({ subs = true }) => {
  const { fps } = useVideoConfig();
  // фон по умолчанию — теплый Pixar
  return (
    <AbsoluteFill style={{ background: "#FFF6E0" }}>
      {/* Аудио для Pixar-версии пока опционально — если сгенерируешь voice_track-pixar.mp3, раскомментируй:
          <Audio src={staticFile("audio/voice_track-pixar.mp3")} />
          <Audio src={staticFile("audio/music_ducked.mp3")} />
      */}
      {sceneRangesPixar().map((r) => {
        const Scene = (PIXAR_SCENES[r.id] ?? PIXAR_SCENES["_placeholder"]) as React.FC<SceneProps>;
        return (
          <Sequence
            key={r.id}
            from={Math.round(r.start * fps)}
            durationInFrames={Math.round((r.end - r.start) * fps)}
            name={`Pixar ${r.id}`}
          >
            <Scene sceneId={r.id} lines={r.lines} sceneStart={r.start} />
            {/* Персонажи — Pixar-версия, прячем на заставке */}
            {r.id !== "0.2" && (
              <PixarCharacters
                lines={r.lines as any}
                sceneStart={r.start}
                hideAfter={r.id === "8.2" ? r.lines[r.lines.length - 1].end - r.start + 0.7 : undefined}
              />
            )}
          </Sequence>
        );
      })}
      {subs && <Subtitles lines={(timing as any).cues} />}
    </AbsoluteFill>
  );
};
