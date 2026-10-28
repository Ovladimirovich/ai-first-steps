import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C } from "../theme";
import type { Line } from "../Main";

// Бит и Маша. Рот говорящего «двигается» — по амплитуде синуса, пока идёт его реплика.
export const Characters: React.FC<{ lines: Line[]; sceneStart: number; hideAfter?: number }> = ({ lines, sceneStart, hideAfter }) => {
  const { fps } = useVideoConfig();
  const f = useCurrentFrame();
  const t = sceneStart + f / fps;
  const speaking = lines.find((l) => t >= l.start && t <= l.end)?.who;
  const mouth = (who: string) => (speaking === who ? 4 + 6 * Math.abs(Math.sin(f * 0.7)) : 2);
  const floatY = Math.sin(f / 18) * 8;
  const blink = f % 120 > 114 ? 0.1 : 1;
  const enter = interpolate(f, [0, 18], [120, 0], { extrapolateRight: "clamp" });
  if (hideAfter !== undefined && f / fps > hideAfter) return null;
  const wave = hideAfter !== undefined ? Math.sin(f / 5) * 6 : 0;
  return (
    <>
      <svg viewBox="0 0 200 200" style={{ position: "absolute", left: 1300, top: 640 + floatY, width: 300, transform: `translateX(${enter}px) rotate(${wave}deg)` }}>
        <line x1="100" y1="40" x2="100" y2="12" stroke={C.teal} strokeWidth="6" />
        <circle cx="100" cy="12" r="10" fill={C.yellow} opacity={0.5 + 0.5 * Math.abs(Math.sin(f / 10))} />
        <rect x="30" y="40" width="140" height="120" rx="28" fill={C.teal} />
        <rect x="48" y="60" width="104" height="70" rx="14" fill={C.dark} />
        <rect x="68" y={92 - 12 * blink} width="18" height={24 * blink} rx="4" fill={C.teal} />
        <rect x="114" y={92 - 12 * blink} width="18" height={24 * blink} rx="4" fill={C.teal} />
        <ellipse cx="100" cy="117" rx="18" ry={mouth("b")} fill={C.teal} />
        <rect x="60" y="160" width="26" height="22" rx="6" fill="#1aa89c" /><rect x="114" y="160" width="26" height="22" rx="6" fill="#1aa89c" />
      </svg>
      <svg viewBox="0 0 160 240" style={{ position: "absolute", left: 1620, top: 600, width: 250, transform: `translateX(${enter}px)` }}>
        <rect x="45" y="110" width="70" height="90" rx="20" fill={C.coral} />
        <rect x="55" y="195" width="20" height="40" rx="6" fill="#3b4a7a" /><rect x="85" y="195" width="20" height="40" rx="6" fill="#3b4a7a" />
        <circle cx="80" cy="70" r="38" fill="#f6d2b8" />
        <path d="M42 70 q0 -45 38 -45 q38 0 38 45 q-10 -20 -38 -20 q-28 0 -38 20z" fill="#5a3a2a" />
        <circle cx="66" cy="72" r="4" /><circle cx="94" cy="72" r="4" />
        <ellipse cx="80" cy="90" rx="10" ry={mouth("m")} fill="#7a2a2a" />
        <rect x="100" y="135" width="34" height="46" rx="4" fill={C.dark} stroke="#aab" strokeWidth="2" />
      </svg>
    </>
  );
};
