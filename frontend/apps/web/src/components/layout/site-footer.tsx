import { useTranslations } from "next-intl";

export function SiteFooter() {
  const t = useTranslations("common");
  return (
    <footer className="mt-10 border-t border-border">
      <div className="container flex flex-col items-center justify-between gap-2 py-5 text-sm md:flex-row">
        <p className="text-muted-foreground" lang="en">
          2026 &copy; <span className="text-secondary-foreground">analysisACE</span>
        </p>
        <p className="text-center text-muted-foreground md:text-end">{t("disclaimer")}</p>
      </div>
    </footer>
  );
}
