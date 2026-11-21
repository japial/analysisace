import { useTranslations } from "next-intl";
import { Fragment, type ReactNode } from "react";

import { Link } from "@/i18n/navigation";

export interface Crumb {
  label: string;
  /** Omit for the current page. */
  href?: string;
}

interface Props {
  title: string;
  description?: string;
  breadcrumbs?: Crumb[];
  /** Buttons shown on the right. */
  children?: ReactNode;
}

/** Metronic Layout 9 page toolbar: title, breadcrumb trail and optional actions. */
export function Toolbar({ title, description, breadcrumbs = [], children }: Props) {
  const t = useTranslations("common");
  return (
    <div className="container">
      <div className="flex flex-wrap items-center justify-between gap-3 py-7">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-medium text-mono">{title}</h1>
          {breadcrumbs.length > 0 && (
            <nav aria-label={t("breadcrumb")} className="flex flex-wrap items-center gap-1 text-sm">
              {breadcrumbs.map((crumb, index) => (
                <Fragment key={`${crumb.label}-${index}`}>
                  {index > 0 && <span className="text-muted-foreground">/</span>}
                  {crumb.href ? (
                    <Link href={crumb.href} className="text-secondary-foreground hover:text-primary">
                      {crumb.label}
                    </Link>
                  ) : (
                    <span aria-current="page" className="text-mono">
                      {crumb.label}
                    </span>
                  )}
                </Fragment>
              ))}
            </nav>
          )}
          {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
        </div>
        {children && <div className="flex flex-wrap items-center gap-2.5">{children}</div>}
      </div>
    </div>
  );
}
