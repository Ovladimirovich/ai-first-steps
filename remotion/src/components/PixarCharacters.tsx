import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { P } from "../pixarTheme";
import type { Line } from "../Main";

// Pixar-версия Бита и Маши — объём через градиенты, тени, блики, SSS-эффект
export const PixarCharacters: React.FC<{ lines: Line[]; sceneStart: number; hideAfter?: number }> = ({ lines, sceneStart, hideAfter }) => {
  const { fps } = useVideoConfig();
  const f = useCurrentFrame();
  const t = sceneStart + f / fps;
  const speaking = lines.find((l) => t >= l.start && t <= l.end)?.who;
  const mouth = (who: string) => (speaking === who ? 4 + 7 * Math.abs(Math.sin(f * 0.68)) : 2.2);
  const floatY = Math.sin(f / 20) * 6;
  const blink = f % 130 > 124 ? 0.12 : 1;
  const enter = interpolate(f, [0, 20], [140, 0], { extrapolateRight: "clamp" });
  if (hideAfter !== undefined && f / fps > hideAfter) return null;
  const wave = hideAfter !== undefined ? Math.sin(f / 5) * 5 : 0;

  return (
    <>
      {/* БИТ — бирюзовый кубик, теперь с объёмом */}
      <div style={{
        position: "absolute", left: 1300, top: 640 + floatY, width: 320, height: 260,
        transform: `translateX(${enter}px) rotate(${wave}deg)`,
        filter: "drop-shadow(0 22px 30px rgba(0,0,0,.35))",
      }}>
        <svg viewBox="0 0 320 260" width="320" height="260" style={{ overflow: "visible" }}>
          {/* тень на пол */}
          <ellipse cx="160" cy="250" rx="90" ry="14" fill="#000" opacity={0.22} />
          {/* антенна */}
          <line x1="160" y1="38" x2="160" y2="12" stroke="#2EE6D6" strokeWidth="7" strokeLinecap="round" />
          <circle cx="160" cy="12" r="13" fill={P.yellow} style={{ filter: "drop-shadow(0 0 10px #FFD23F)" }} opacity={0.55 + 0.45 * Math.abs(Math.sin(f / 10))} />
          <circle cx="160" cy="12" r="5" fill="#FFFDE0" />
          {/* корпус — градиент + блик */}
          <defs>
            <linearGradient id="bitBody" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#5EF0E0" />
              <stop offset="55%" stopColor="#2EE6D6" />
              <stop offset="100%" stopColor="#1AA89C" />
            </linearGradient>
            <linearGradient id="bitShade" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="rgba(0,0,0,.22)" />
              <stop offset="100%" stopColor="transparent" />
            </linearGradient>
          </defs>
          <rect x="18" y="34" width="284" height="176" rx="36" fill="url(#bitBody)" stroke="rgba(255,255,255,.22)" strokeWidth="2" />
          <rect x="18" y="34" width="284" height="176" rx="36" fill="url(#bitShade)" opacity={0.9} />
          {/* блик сверху */}
          <rect x="36" y="44" width="248" height="22" rx="11" fill="rgba(255,255,255,.34)" />
          {/* царапинки как на Pixar-рендере */}
          <path d="M40 170 l22 -6 M260 150 l18 8" stroke="rgba(0,0,0,.16)" strokeWidth="3" strokeLinecap="round" />
          {/* экран */}
          <rect x="52" y="64" width="216" height="118" rx="22" fill="#0D1526" stroke="rgba(255,255,255,.14)" strokeWidth="2" />
          <rect x="52" y="64" width="216" height="28" rx="11" fill="rgba(255,255,255,.07)" />
          {/* глаза */}
          <rect x="86" y={96 - 10 * blink} width="34" height={34 * blink} rx="10" fill="#2EE6D6" style={{ filter: "drop-shadow(0 0 8px #2EE6D6)" }} />
          <rect x="200" y={96 - 10 * blink} width="34" height={34 * blink} rx="10" fill="#2EE6D6" style={{ filter: "drop-shadow(0 0 8px #2EE6D6)" }} />
          <circle cx="103" cy="108" r="5" fill="#fff" opacity={0.9} />
          <circle cx="217" cy="108" r="5" fill="#fff" opacity={0.9} />
          {/* брови */}
          <path d="M84 88 q14 -8 28 0" stroke="#2EE6D6" strokeWidth="4" fill="none" strokeLinecap="round" opacity={0.9} />
          <path d="M208 88 q14 -8 28 0" stroke="#2EE6D6" strokeWidth="4" fill="none" strokeLinecap="round" opacity={0.9} />
          {/* рот */}
          <ellipse cx="160" cy="146" rx="22" ry={mouth("b")} fill="#2EE6D6" />
          {/* руки-ноги с объёмом */}
          <ellipse cx="54" cy="162" rx="26" ry="26" fill="#1AA89C" stroke="rgba(0,0,0,.12)" strokeWidth="2" />
          <rect x="28" y="162" width="52" height="54" rx="18" fill="#2EE6D6" stroke="rgba(255,255,255,.18)" strokeWidth="2" />
          <ellipse cx="266" cy="180" rx="22" ry="22" fill="#1AA89C" />
          <rect x="240" y="172" width="44" height="44" rx="14" fill="#2EE6D6" />
          {/* гусеницы */}
          <rect x="54" y="212" width="64" height="26" rx="10" fill="#0F2A2A" stroke="rgba(255,255,255,.12)" />
          <rect x="204" y="212" width="64" height="26" rx="10" fill="#0F2A2A" />
        </svg>
      </div>

      {/* МАША — Pixar-девочка: мягкие тени, румянец SSS, волосы с бликом */}
      <div style={{
        position: "absolute", left: 1620, top: 600, width: 260, height: 360,
        transform: `translateX(${enter}px)`,
        filter: "drop-shadow(0 18px 28px rgba(0,0,0,.32))",
      }}>
        <svg viewBox="0 0 260 360" width="260" height="360" style={{ overflow: "visible" }}>
          <ellipse cx="130" cy="348" rx="70" ry="12" fill="#000" opacity={0.18} />
          {/* ноги */}
          <rect x="78" y="264" width="36" height="74" rx="12" fill="#3B4A7A" />
          <rect x="142" y="264" width="36" height="74" rx="12" fill="#3B4A7A" />
          <rect x="70" y="334" width="52" height="18" rx="8" fill="#1B2A4A" />
          <rect x="136" y="334" width="52" height="18" rx="8" fill="#1B2A4A" />
          {/* худи — градиент + блик */}
          <defs>
            <linearGradient id="hoodie" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#FFB84D" />
              <stop offset="50%" stopColor="#E8A23B" />
              <stop offset="100%" stopColor="#C9851A" />
            </linearGradient>
          </defs>
          <rect x="44" y="128" width="172" height="148" rx="34" fill="url(#hoodie)" stroke="rgba(255,255,255,.22)" strokeWidth="2" />
          <rect x="62" y="138" width="136" height="18" rx="9" fill="rgba(255,255,255,.22)" />
          {/* руки */}
          <rect x="18" y="150" width="44" height="88" rx="18" fill="#E8A23B" />
          <rect x="198" y="150" width="44" height="88" rx="18" fill="#E8A23B" />
          {/* планшет */}
          <rect x="158" y="178" width="86" height="62" rx="8" fill="#0D1526" stroke="#AAB" strokeWidth="3" />
          <rect x="164" y="184" width="74" height="46" rx="4" fill="#2EE6D6" opacity={0.9} />
          {/* голова — SSS румянец */}
          <circle cx="130" cy="78" r="58" fill="#F9D6BA" stroke="rgba(0,0,0,.06)" strokeWidth="2" />
          <circle cx="108" cy="92" r="10" fill="#FF8A8A" opacity={0.28} />
          <circle cx="152" cy="92" r="10" fill="#FF8A8A" opacity={0.28} />
          {/* волосы — объем */}
          <path d="M54 78 q0 -72 76 -62 q72 -6 78 58 q-18 -22 -46 -22 q-30 14 -68 8 q-26 6 -40 18z" fill="#5A3A2A" />
          <path d="M190 34 q34 22 24 68 q-10 -18 -22 -24" fill="#6E4A32" />
          {/* хвостик */}
          <ellipse cx="204" cy="44" rx="28" ry="38" fill="#5A3A2A" />
          <ellipse cx="214" cy="34" rx="10" ry="14" fill="#7A5A3A" opacity={0.6} />
          {/* глаза */}
          <ellipse cx="108" cy="78" rx="11" ry={13 * blink} fill="#2B1A0E" />
          <ellipse cx="152" cy="78" rx="11" ry={13 * blink} fill="#2B1A0E" />
          <circle cx="112" cy="72" r="4" fill="#fff" />
          <circle cx="156" cy="72" r="4" fill="#fff" />
          <circle cx="110" cy="80" r="2" fill="#7ACBFF" />
          <circle cx="154" cy="80" r="2" fill="#7ACBFF" />
          {/* рот */}
          <ellipse cx="130" cy="108" rx="14" ry={mouth("m")} fill="#7A2A2A" />
          <path d="M118 102 q12 6 24 0" stroke="#5A1A1A" strokeWidth="2" fill="none" strokeLinecap="round" />
        </svg>
      </div>
    </>
  );
};
