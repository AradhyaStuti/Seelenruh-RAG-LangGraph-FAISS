import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { LANGS, getLang, setLang, subscribeLang } from "@/lib/lang";
import { cn } from "@/lib/utils";

export function LangToggle() {
  const [code, setCode] = useState(() => getLang());
  const [open, setOpen] = useState(false);

  useEffect(() => subscribeLang(setCode), []);

  const current = LANGS.find((l) => l.code === code) || LANGS[0];

  return (
    <div className="relative">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setOpen((v) => !v)}
            className="rounded-full h-9 px-3 text-[11px] gap-1 hover:bg-primary/10 hover:text-primary"
            aria-label="Language"
          >
            <span className="font-mono uppercase">{current.code === "hi-roman" ? "HIN" : current.code}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent>Reply language</TooltipContent>
      </Tooltip>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <ul className="absolute right-0 top-full mt-2 z-40 w-36 rounded-2xl bg-card/95 backdrop-blur-xl border border-border/40 petal-shadow py-1.5">
            {LANGS.map((l) => (
              <li key={l.code}>
                <button
                  type="button"
                  onClick={() => {
                    setLang(l.code);
                    setOpen(false);
                  }}
                  className={cn(
                    "w-full text-left px-3 py-2 text-xs hover:bg-primary/10 transition-colors whitespace-nowrap",
                    l.code === code && "bg-primary/15 text-primary font-medium"
                  )}
                >
                  {l.label}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
