import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FONT } from "../theme";
export const BOTS = {
  chatgpt: { name: "ChatGPT", sub: "OpenAI · США · 2022", bg: "#1f5e46" },
  alice:   { name: "Алиса AI", sub: "Яндекс · Россия · 2017", bg: "#4a2f7a" },
  giga:    { name: "GigaChat", sub: "Сбер · Россия · 2023", bg: "#1f5a5a" },
} as const;
// Нейтральная карточка без товарных знаков: название, компания, год, список фактов. Факты появляются по очереди (delay в кадрах).
export const BotCard: React.FC<{ bot: keyof typeof BOTS; x: number; y: number; w: number; h?: number; facts?: { t: string; at: number }[]; delay?: number; big?: boolean }> = ({ bot, x, y, w, h, facts = [], delay = 0, big }) => {
  const { fps } = useVideoConfig(); const f = useCurrentFrame();
  const s = spring({ frame: f - delay, fps, config: { damping: 12, stiffness: 120 } });
  const b = BOTS[bot];
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h, background: b.bg, borderRadius: 28, padding: 34, fontFamily: FONT, color: "#fff", boxShadow: "0 12px 40px #0006", opacity: s, transform: `translateY(${(1 - s) * 40}px)` }}>
      <div style={{ fontSize: big ? 64 : 44, fontWeight: 800 }}>{b.name}</div>
      <div style={{ fontSize: big ? 30 : 21, opacity: 0.8, whiteSpace: "nowrap", marginBottom: 24 }}>{b.sub}</div>
      {facts.map((fa, i) => {
        const fs = spring({ frame: f - fa.at, fps, config: { damping: 14 } });
        return <div key={i} style={{ fontSize: big ? 38 : 28, lineHeight: 1.35, margin: "10px 0", opacity: fs, transform: `translateX(${(1 - fs) * -30}px)` }}>{fa.t}</div>;
      })}
    </div>
  );
};
