// Кот-космонавт — сквозной ассет (сцены 0.1, 5.2, 5.3, 8.2)
export const Cat: React.FC<{ style?: React.CSSProperties; egypt?: boolean }> = ({ style, egypt }) => (
  <svg viewBox="0 0 320 320" style={style}>
    <rect width="320" height="320" fill={egypt ? "#e8c882" : "#060a1a"} />
    {egypt ? <polygon points="40,290 160,90 280,290" fill="#c9a24e" /> : <circle cx="250" cy="70" r="30" fill="#ddd" />}
    <ellipse cx="160" cy="290" rx="200" ry="60" fill={egypt ? "#d9b56a" : "#8d8d9c"} />
    {!egypt && <circle cx="160" cy="170" r="70" fill="#dff6ff" opacity=".35" stroke="#fff" strokeWidth="4" />}
    {egypt && <path d="M105 160 q55 -70 110 0 l10 60 h-130z" fill="#2a5aa8" />}
    <circle cx="160" cy="175" r="42" fill="#f2a65a" />
    <polygon points="125,150 135,115 155,145" fill="#f2a65a" /><polygon points="195,150 185,115 165,145" fill="#f2a65a" />
    <circle cx="145" cy="172" r="5" /><circle cx="175" cy="172" r="5" />
    {egypt && <><path d="M135 165 l-14 -3" stroke="#000" strokeWidth="3"/><path d="M185 165 l14 -3" stroke="#000" strokeWidth="3"/></>}
    <path d="M152 188 q8 8 16 0" stroke="#000" strokeWidth="3" fill="none" />
    <rect x="115" y="235" width="90" height="50" rx="14" fill={egypt ? "#d4af37" : "#fff"} />
  </svg>
);
