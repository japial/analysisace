import { cn } from "@/lib/utils";

/**
 * The analysisACE logo system, from the owner's brand artifact (docs/DECISIONS.md, D14).
 * Light: navy "A", white bars, teal accent bar. Dark: white "A", navy bars, deep-teal accent bar.
 * The marks are inline SVG so they follow the theme without a second image file.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className={cn("size-9 shrink-0", className)}>
      <path d="M32 6L60 58H4Z" className="fill-brand-navy dark:fill-white" />
      <rect x="17" y="42" width="7" height="10" rx="1.5" className="fill-white dark:fill-brand-navy" />
      <rect x="40" y="42" width="7" height="10" rx="1.5" className="fill-white dark:fill-brand-navy" />
      <rect
        x="28.5"
        y="30"
        width="7"
        height="22"
        rx="1.5"
        className="fill-brand-teal dark:fill-brand-teal-deep"
      />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span
      lang="en"
      className={cn(
        "font-display font-bold leading-none tracking-[-0.035em] text-brand-navy dark:text-white",
        className,
      )}
    >
      analysis<span className="text-brand-teal-deep dark:text-brand-teal">ACE</span>
    </span>
  );
}

interface LogoProps {
  className?: string;
  markClassName?: string;
  wordmarkClassName?: string;
  /** "sm" hides the wordmark on phones, where the header has no room for it. */
  wordmark?: "always" | "sm";
}

/** Mark plus wordmark. The accessible name comes from the visible text. */
export function Logo({
  className,
  markClassName,
  wordmarkClassName,
  wordmark = "always",
}: LogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark className={markClassName} />
      <Wordmark
        className={cn("text-xl", wordmark === "sm" && "hidden sm:inline", wordmarkClassName)}
      />
    </span>
  );
}
