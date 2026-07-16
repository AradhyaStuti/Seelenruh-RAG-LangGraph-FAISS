import { cn } from "@/lib/utils";

export function QuickReplies({ prompts, onSelect, disabled, className }) {
  if (!prompts.length) return null;
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {prompts.map((p, i) => (
        <button
          key={p}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(p)}
          style={{ animationDelay: `${i * 55}ms` }}
          className={cn(
            "rounded-full border border-border/55 bg-card/75 px-4 py-1.5 text-xs font-medium",
            "text-foreground/70 transition-all duration-200 animate-fade-in",
            "hover:border-primary/50 hover:bg-primary/8 hover:text-primary hover:-translate-y-px",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
            "disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0"
          )}
        >
          {p}
        </button>
      ))}
    </div>
  );
}
