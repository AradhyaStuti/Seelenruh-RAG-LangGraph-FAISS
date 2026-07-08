const defaults = {
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function BlossomLogo(props) {
  const angles = [-60, -30, 0, 30, 60];
  return (
    <svg {...defaults} {...props}>
      <defs>
        <linearGradient id="lotusFill" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="hsl(var(--accent))" stopOpacity="0.9" />
          <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0.95" />
        </linearGradient>
      </defs>

      {/* water line beneath the lotus */}
      <path
        d="M3 19c2 1.2 5 1.8 9 1.8s7-.6 9-1.8"
        stroke="hsl(var(--primary))"
        strokeOpacity="0.45"
        fill="none"
      />

      {/* 5 petals fanned upward */}
      {angles.map((deg) => (
        <path
          key={deg}
          d="M0,-9 C2.4,-5 2.4,-1 0,2 C-2.4,-1 -2.4,-5 0,-9 Z"
          transform={`translate(12 16) rotate(${deg})`}
          fill="url(#lotusFill)"
          stroke="hsl(var(--primary))"
          strokeOpacity="0.55"
          strokeWidth="1"
        />
      ))}

      {/* pistil */}
      <circle
        cx="12"
        cy="16"
        r="1.6"
        fill="hsl(var(--card))"
        stroke="hsl(var(--primary))"
        strokeOpacity="0.7"
      />
    </svg>
  );
}

export function PetalHeart(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M12 20s-6.5-4-8.2-8.4C2.7 9 4.1 6 7 6c1.9 0 3.4 1 5 3 1.6-2 3.1-3 5-3 2.9 0 4.3 3 3.2 5.6C18.5 16 12 20 12 20Z" />
      <path d="M9 11c.6.6 1.4 1 2.4 1.2M15 11c-.6.6-1.4 1-2.4 1.2" strokeOpacity="0.6" />
    </svg>
  );
}

export function FeatherScale(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M5 19c4-1 7.5-2.6 10-5.2 2.5-2.5 3.5-5.4 3-8.8-3.4-.5-6.3.5-8.8 3C6.6 10.5 5 14 4 18l1 1Z" />
      <path d="M5 19l5-5" />
      <path d="M9 9l6 6" strokeOpacity="0.55" />
    </svg>
  );
}

export function SunBloom(props) {
  return (
    <svg {...defaults} {...props}>
      <circle cx="12" cy="12" r="2.6" fill="hsl(var(--primary) / 0.18)" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
        <ellipse
          key={deg}
          cx="12"
          cy="6"
          rx="1.6"
          ry="2.8"
          transform={`rotate(${deg} 12 12)`}
          fill="hsl(var(--primary) / 0.22)"
        />
      ))}
    </svg>
  );
}

export function GentleShield(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M12 3.2 5 5.6V12c0 4.3 3 7.6 7 8.8 4-1.2 7-4.5 7-8.8V5.6L12 3.2Z" fill="hsl(var(--primary) / 0.12)" />
      <path d="M12 10.4c-.7-1-1.6-1.4-2.5-1.1-1 .3-1.6 1.4-1.3 2.5.3 1.2 1.4 2.2 3.8 3.8 2.4-1.6 3.5-2.6 3.8-3.8.3-1.1-.3-2.2-1.3-2.5-.9-.3-1.8.1-2.5 1.1Z" />
    </svg>
  );
}

export function SoftSend(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M21 4 3 11l7 2 2 7 9-16Z" fill="hsl(var(--primary-foreground) / 0.18)" />
      <path d="m10 13 4-4" strokeOpacity="0.7" />
    </svg>
  );
}

export function SoftMic(props) {
  return (
    <svg {...defaults} {...props}>
      <rect x="9" y="3" width="6" height="11" rx="3" fill="hsl(var(--primary-foreground) / 0.18)" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7" />
    </svg>
  );
}

export function SoftMoon(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" fill="currentColor" fillOpacity="0.1" />
      <circle cx="17" cy="7" r="0.8" fill="currentColor" fillOpacity="0.6" />
      <circle cx="20" cy="11" r="0.5" fill="currentColor" fillOpacity="0.5" />
    </svg>
  );
}

export function SoftSun(props) {
  return (
    <svg {...defaults} {...props}>
      <circle cx="12" cy="12" r="4.2" fill="currentColor" fillOpacity="0.15" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4" />
    </svg>
  );
}

export function HeartBookmark(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M6 4h12v17l-6-4-6 4V4Z" fill="hsl(var(--primary) / 0.12)" />
      <path d="M12 13s-2.5-1.4-3.2-3.2c-.4-1 .1-2 1.1-2.2.7-.2 1.4.1 2.1 1 .7-.9 1.4-1.2 2.1-1 1 .2 1.5 1.2 1.1 2.2C14.5 11.6 12 13 12 13Z" />
    </svg>
  );
}

export function BreathLungs(props) {
  return (
    <svg {...defaults} {...props}>
      <circle cx="12" cy="12" r="9.5" strokeOpacity="0.3" />
      <circle cx="12" cy="12" r="6.5" strokeOpacity="0.55" />
      <circle cx="12" cy="12" r="3.5" fill="currentColor" fillOpacity="0.18" />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" />
    </svg>
  );
}

export function SoftSpeaker(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M5 9v6h3l5 4V5L8 9H5Z" fill="currentColor" fillOpacity="0.18" />
      <path d="M16 9c1 1 1 5 0 6M18.5 7c2 2 2 8 0 10" strokeOpacity="0.7" />
    </svg>
  );
}

export function SoftStop(props) {
  return (
    <svg {...defaults} {...props}>
      <rect x="6" y="6" width="12" height="12" rx="3" fill="currentColor" fillOpacity="0.18" />
    </svg>
  );
}

export function SoftCopy(props) {
  return (
    <svg {...defaults} {...props}>
      <rect x="8" y="8" width="11" height="11" rx="2.5" fill="currentColor" fillOpacity="0.1" />
      <rect x="5" y="5" width="11" height="11" rx="2.5" />
    </svg>
  );
}

export function SoftCheck(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M5 12.5 10 17l9-10" />
    </svg>
  );
}

export function SoftRefresh(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M4 12a8 8 0 0 1 14-5.3" />
      <path d="M20 12a8 8 0 0 1-14 5.3" />
      <path d="M14 6h4V2" />
      <path d="M10 18H6v4" />
    </svg>
  );
}

export function SoftUser(props) {
  return (
    <svg {...defaults} {...props}>
      <circle cx="12" cy="8.5" r="3.5" fill="currentColor" fillOpacity="0.15" />
      <path d="M4.5 20c.5-3.5 3.5-6 7.5-6s7 2.5 7.5 6" />
    </svg>
  );
}


export function SoftInfo(props) {
  return (
    <svg {...defaults} {...props}>
      <circle cx="12" cy="12" r="9" fill="currentColor" fillOpacity="0.1" />
      <path d="M12 11v5M12 8v.5" />
    </svg>
  );
}

export function SoftClose(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  );
}

export function SoftEye(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" fill="currentColor" fillOpacity="0.1" />
      <circle cx="12" cy="12" r="3" fill="currentColor" fillOpacity="0.18" />
    </svg>
  );
}

export function SoftEyeOff(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M2 12s3.5-7 10-7c2.5 0 4.7 1 6.5 2.3M22 12s-3.5 7-10 7c-2.5 0-4.7-1-6.5-2.3" fill="none" fillOpacity="0.1" />
      <path d="M9.5 9.5a3 3 0 0 0 4 4M14.5 14.5a3 3 0 0 0-4-4" strokeOpacity="0.7" />
      <path d="m3 3 18 18" />
    </svg>
  );
}

export function SoftPhone(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M5.5 4.5h3l1.8 4.2-2.1 1.5a11 11 0 0 0 5.6 5.6l1.5-2.1 4.2 1.8v3a2 2 0 0 1-2.2 2A16 16 0 0 1 3.5 6.7a2 2 0 0 1 2-2.2Z" fill="currentColor" fillOpacity="0.12" />
    </svg>
  );
}

export function MoodFace({ mood, ...props }) {
  const path = {
    joyful:  "M8 14c1.2 1.2 2.5 1.8 4 1.8s2.8-.6 4-1.8",
    calm:    "M8 14.5c1.2.8 2.5 1.2 4 1.2s2.8-.4 4-1.2",
    tired:   "M8 15h8",
    anxious: "M8 15.5c1-.5 2-.5 4-1.5s3 1 4 1.5",
    sad:     "M8 16c1.2-1.2 2.5-1.8 4-1.8s2.8.6 4 1.8",
  }[mood];
  return (
    <svg {...defaults} {...props}>
      <circle cx="12" cy="12" r="9" fill="hsl(var(--primary) / 0.14)" />
      <circle cx="9" cy="10.5" r={mood === "tired" ? 0.4 : 0.9} fill="currentColor" />
      <circle cx="15" cy="10.5" r={mood === "tired" ? 0.4 : 0.9} fill="currentColor" />
      {mood === "tired" && <path d="M7.5 10.5h3M13.5 10.5h3" />}
      <path d={path} />
    </svg>
  );
}

export function SoftAlert(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M12 4 2.5 20h19L12 4Z" fill="currentColor" fillOpacity="0.12" />
      <path d="M12 10v4M12 17v.5" />
    </svg>
  );
}

export function SoftSiren(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M5 17a7 7 0 0 1 14 0v2H5v-2Z" fill="currentColor" fillOpacity="0.12" />
      <path d="M12 6V3M5 8 3 6M19 8l2-2" />
    </svg>
  );
}

export function SoftFlame(props) {
  return (
    <svg {...defaults} {...props}>
      <path d="M12 3c0 4 5 5 5 10a5 5 0 1 1-10 0c0-3 2-4 2-7 1 1 2 1 3-3Z" fill="currentColor" fillOpacity="0.14" />
    </svg>
  );
}
