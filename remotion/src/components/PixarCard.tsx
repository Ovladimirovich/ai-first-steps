import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { P, PFONT } from "../pixarTheme";

// Объёмная Pixar-карточка: скос, мягкая тень, блик сверху, пружинка
export const PixarCard: React.FC<{
  x: number; y: number; w: number;
  delay?: number; bg?: string; size?: number;
  children: React.ReactNode
}> = ({ x, y, w, delay = 0, bg = "#243A66", size = 40, children }) => {
  const { fps } = useVideoConfig();
  const s = spring({ frame: useCurrentFrame() - delay, fps, config: { damping: 13, stiffness: 140 } });
  return (
    <div style={{
      position: "absolute", left: x, top: y, width: w,
      background: bg,
      borderRadius: 28,
      padding: "30px 38px",
      fontFamily: PFONT, fontSize: size, lineHeight: 1.32, color: "#F4F6FA",
      boxShadow: "0 20px 60px rgba(0,0,0,.32), 0 2px 0 rgba(255,255,255,.14) inset, 0 -6px 14px rgba(0,0,0,.18) inset",
      border: "1px solid rgba(255,255,255,.08)",
      opacity: s,
      transform: `translateY(${(1 - s) * 36}px) scale(${0.92 + 0.08 * s})`,
    }}>
      {/* блик */}
      <div style={{
        position: "absolute", left: 18, right: 18, top: 0, height: 18,
        background: "linear-gradient(180deg, rgba(255,255,255,.18), transparent)",
        borderRadius: "28px 28px 0 0", pointerEvents: "none"
      }} />
      {children}
    </div>
  );
};

export const PixarHL: React.FC<{ children: React.ReactNode }> = ({ children }) =>
  <span style={{ color: P.yellow, fontWeight: 800, textShadow: "0 2px 10px rgba(255,210,63,.45)" }}>{children}</span>;

export const PixarTitle: React.FC<{ children: React.ReactNode; light?: boolean }> = ({ children, light }) => (
  <div style={{
    position: "absolute", top: 44, left: 0, right: 0, textAlign: "center",
    fontFamily: PFONT, fontWeight: 800, fontSize: 58,
    color: light ? "#1B2A4A" : "#fff",
    textShadow: light ? "0 2px 0 #fff, 0 10px 28px rgba(0,0,0,.12)" : "0 4px 22px rgba(0,0,0,.45)",
    letterSpacing: -0.5,
  }}>{children}</div>
);
