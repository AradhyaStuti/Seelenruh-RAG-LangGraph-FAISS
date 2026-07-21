const PERSONA_COLORS = {
  Usha: "#7CB9E8",
  Umang: "#C9B38A",
  Aarogya: "#8FC9A3",
  Raksha: "#E87C7C",
};

export function AppFooter() {
  return (
    <footer className="w-full max-w-5xl mx-auto px-4 sm:px-6 pb-8 pt-2">
      <div className="flex flex-col items-center gap-2.5">
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground/40 font-medium">
          {Object.entries(PERSONA_COLORS).map(([name, color], i, arr) => (
            <span key={name} className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full inline-block" style={{ background: color, opacity: 0.7 }} />
              {name}
              {i < arr.length - 1 && <span className="ml-1.5 opacity-30">·</span>}
            </span>
          ))}
        </div>
        <p className="text-[11px] text-muted-foreground/35 leading-relaxed text-center max-w-lg">
          Seelenruh provides supportive information only — not a substitute for professional medical, legal, or emergency advice.
          In a crisis, contact local emergency services or a qualified professional.
        </p>
        <p className="text-[10px] text-muted-foreground/20 tracking-widest uppercase font-medium">
          seelenruh · peace of the soul
        </p>
      </div>
    </footer>
  );
}
