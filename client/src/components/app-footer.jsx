export function AppFooter() {
  return (
    <footer className="w-full max-w-5xl mx-auto px-4 sm:px-6 pb-8 pt-4">
      <div className="flex flex-col items-center gap-2">
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/35 font-medium">
          <span>Usha</span>
          <span className="opacity-50">·</span>
          <span>Umang</span>
          <span className="opacity-50">·</span>
          <span>Aarogya</span>
          <span className="opacity-50">·</span>
          <span>Raksha</span>
        </div>
        <p className="text-[11px] text-muted-foreground/40 leading-relaxed text-center max-w-lg">
          Seelenruh provides supportive information only — not a substitute for professional medical, legal, or emergency advice.
          In a crisis, contact local emergency services or a qualified professional.
        </p>
        <p className="text-[10px] text-muted-foreground/25 tracking-wide">
          seelenruh · peace of the soul
        </p>
      </div>
    </footer>
  );
}
