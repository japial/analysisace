import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";

export default function NotFound() {
  const t = useTranslations("common");
  return (
    <div className="container py-16">
      <h1 className="text-2xl font-semibold text-mono">{t("notFoundTitle")}</h1>
      <p className="mt-2 text-secondary-foreground">{t("notFoundBody")}</p>
      <Button asChild className="mt-5">
        <Link href="/">{t("backHome")}</Link>
      </Button>
    </div>
  );
}
