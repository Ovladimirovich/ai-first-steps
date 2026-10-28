import { useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT } from "../theme";
type Cue = { who: string; text: string; start: number; end: number };

export const Subtitles: React.FC<{ lines: Cue[] }> = ({ lines }) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const cur = lines.find((l) => t >= l.start && t <= l.end + 0.15);
  if (!cur) return null;
  const who = cur.who === "b" ? "Бит" : "Маша";
  return (
    <div style={{ position: "absolute", bottom: 40, left: 120, right: 700, textAlign: "center", fontFamily: FONT }}>
      <span style={{ display: "inline-block", background: "rgba(0,0,0,.72)", color: C.white, fontSize: 42, lineHeight: 1.3, padding: "10px 26px", borderRadius: 14 }}>
        <b style={{ color: cur.who === "b" ? C.teal : C.coral, marginRight: 12 }}>{who}:</b>
        {cur.text}
      </span>
    </div>
  );
};
