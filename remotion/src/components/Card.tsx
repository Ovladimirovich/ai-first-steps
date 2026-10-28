import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT } from "../theme";
export const Card: React.FC<{ x: number; y: number; w: number; delay?: number; bg?: string; size?: number; children: React.ReactNode }> = ({ x, y, w, delay = 0, bg = C.panel, size = 40, children }) => {
  const { fps } = useVideoConfig();
  const s = spring({ frame: useCurrentFrame() - delay, fps, config: { damping: 12, stiffness: 120 } });
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, background: bg, borderRadius: 28, padding: "30px 38px", fontFamily: FONT, fontSize: size, lineHeight: 1.3, color: C.white, boxShadow: "0 12px 40px #0006", opacity: s, transform: `translateY(${(1 - s) * 40}px) scale(${0.9 + 0.1 * s})` }}>
      {children}
    </div>
  );
};
export const HL: React.FC<{ children: React.ReactNode }> = ({ children }) => <span style={{ color: C.yellow, fontWeight: 800 }}>{children}</span>;
export const Title: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ position: "absolute", top: 50, left: 0, right: 0, textAlign: "center", fontFamily: FONT, fontWeight: 800, fontSize: 54, color: C.white }}>{children}</div>
);
