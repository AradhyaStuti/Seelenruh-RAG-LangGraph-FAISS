import { SoftInfo } from "@/components/icons";

export function AppFooter() {
  return (
    <footer className="w-full max-w-5xl mx-auto px-4 sm:px-6 pt-6 pb-8 text-center text-xs text-muted-foreground">
      <div className="flex items-start justify-center gap-2.5 rounded-3xl glass petal-shadow px-5 py-3.5">
        <SoftInfo className="h-4 w-4 mt-0.5 shrink-0 text-primary/80" />
        <p className="leading-relaxed text-left sm:text-center text-foreground/75">
          Seelenruh provides supportive information only. It is not a substitute
          for professional medical, legal, or emergency advice. In a crisis,
          please contact local emergency services or a qualified professional.
        </p>
      </div>
    </footer>
  );
}
