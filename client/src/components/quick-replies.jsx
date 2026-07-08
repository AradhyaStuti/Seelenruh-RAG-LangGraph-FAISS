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
          style={{ animationDelay: `${i * 50}ms` }}
          className={cn(
            "rounded-lg border border-[#CBD5E1] bg-white px-3.5 py-1.5 text-xs font-medium",
            "text-[#0F172A] transition-all duration-150 animate-fade-in",
            "hover:border-[#1E3A8A] hover:bg-[#EFF6FF] hover:text-[#1E3A8A]",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          {p}
        </button>
      ))}
    </div>
  );
}
