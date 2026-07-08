import { useEffect, useState } from "react";
import { SoftMoon, SoftSun } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const STORAGE_KEY = "seelenruh:dark-mode";

export function ThemeToggle() {
  const [isDark, setIsDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const prefersDark =
      stored === null
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
        : stored === "true";
    setIsDark(prefersDark);
    document.documentElement.classList.toggle("dark", prefersDark);
    setMounted(true);
  }, []);

  const toggle = () => {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle("dark", next);
    window.localStorage.setItem(STORAGE_KEY, String(next));
  };

  if (!mounted) {
    return (
      <Button variant="ghost" size="icon" aria-hidden className="opacity-0">
        <SoftSun className="h-5 w-5" />
      </Button>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggle}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          className="rounded-full hover:bg-primary/10 hover:text-primary transition"
        >
          {isDark ? <SoftSun className="h-5 w-5" /> : <SoftMoon className="h-5 w-5" />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{isDark ? "Light" : "Dark"}</TooltipContent>
    </Tooltip>
  );
}
