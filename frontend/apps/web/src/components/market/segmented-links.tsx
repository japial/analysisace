/**
 * A row of joined links styled like Metronic's outline toggle group (components/ui/toggle,
 * which is a client module, so its classes are repeated here), for choices that
 * change the URL (a period, an event type). They stay links, with `aria-current` on the
 * chosen one, so they work without scripts and read correctly to screen readers.
 */
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

type Href = Parameters<typeof Link>[0]["href"];

/** Metronic toggle, variant "outline", size "md". */
const OUTLINE_TOGGLE =
  "inline-flex h-8.5 min-w-8.5 shrink-0 items-center justify-center gap-1 border border-input bg-transparent px-2.5 text-[0.8125rem] font-medium ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:z-10 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

export function SegmentedLinks({
  label,
  options,
  className,
}: {
  label: string;
  options: { key: string; label: string; href: Href; current: boolean }[];
  className?: string;
}) {
  return (
    <nav aria-label={label} className={cn("inline-flex max-w-full overflow-x-auto rounded-md shadow-xs", className)}>
      {options.map((option) => (
        <Link
          key={option.key}
          href={option.href}
          scroll={false}
          aria-current={option.current ? "true" : undefined}
          data-state={option.current ? "on" : "off"}
          className={cn(
            OUTLINE_TOGGLE,
            "rounded-none border-s-0 whitespace-nowrap first:rounded-s-md first:border-s last:rounded-e-md",
            "data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary",
          )}
        >
          {option.label}
        </Link>
      ))}
    </nav>
  );
}
