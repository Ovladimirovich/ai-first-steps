import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from "remotion";
import timing from "../public/timing.json";
import { Subtitles } from "./components/Subtitles";
import { Characters } from "./components/Characters";
import { SCENES } from "./scenes";
import { C } from "./theme";

export type Line = (typeof timing.lines)[number];

// Границы сцен вычисляются из реальных таймкодов реплик: сцена длится от первой своей реплики до первой реплики следующей сцены.
export const sceneRanges = () => {
  const ids = [...new Set(timing.lines.map((l) => l.scene))];
  return ids.map((id, i) => {
    const mine = timing.lines.filter((l) => l.scene === id);
    const next = timing.lines.find((l) => l.scene === ids[i + 1]);
    const start = Math.max(0, mine[0].start - 0.8);
    const end = next ? Math.max(0, next.start - 0.8) : timing.total + 9;
    return { id, start, end, lines: mine };
  });
};

export const Main: React.FC<{ subs: boolean }> = ({ subs }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <Audio src={staticFile("audio/voice_track.mp3")} />
      <Audio src={staticFile("audio/music_ducked.mp3")} />
      {sceneRanges().map((r) => {
        const Scene = SCENES[r.id] ?? SCENES["_placeholder"];
        return (
          <Sequence key={r.id} from={Math.round(r.start * fps)} durationInFrames={Math.round((r.end - r.start) * fps)} name={`Сцена ${r.id}`}>
            <Scene sceneId={r.id} lines={r.lines} sceneStart={r.start} />
            {r.id !== "0.2" && <Characters lines={r.lines} sceneStart={r.start} hideAfter={r.id === "8.2" ? r.lines[r.lines.length - 1].end - r.start + 0.7 : undefined} />}
          </Sequence>
        );
      })}
      {subs && <Subtitles lines={timing.cues} />}
    </AbsoluteFill>
  );
};
