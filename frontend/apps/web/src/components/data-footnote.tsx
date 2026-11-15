import { formatDate, type SourceRef } from "@analysisace/core";
import { useLocale, useTranslations } from "next-intl";

import { digitsFor } from "@/lib/locale";

interface Props {
  asOf: string | null;
  sources: SourceRef[];
}

/**
 * Shows when the data is from and where it came from. Every number on a page must be
 * traceable (PRD section 0), so place this under any block of API data.
 */
export function DataFootnote({ asOf, sources }: Props) {
  const t = useTranslations("common");
  const locale = useLocale();
  if (!asOf && sources.length === 0) return null;

  return (
    <footer className="text-sm text-muted-foreground">
      {asOf && (
        <p>
          {t("asOf", {
            date: formatDate(asOf, { language: locale, digits: digitsFor(locale), withTime: true }),
          })}
        </p>
      )}
      {sources.length > 0 && (
        <div className="mt-1">
          <span>{t("sources")}: </span>
          <ul className="inline">
            {sources.map((source, index) => (
              <li key={`${source.name}-${source.fetched_at}`} className="inline">
                {index > 0 && ", "}
                {source.url ? (
                  <a href={source.url} rel="noopener" className="underline hover:text-foreground">
                    {source.name}
                  </a>
                ) : (
                  source.name
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </footer>
  );
}
