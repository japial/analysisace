import { Info } from "lucide-react";
import { useTranslations } from "next-intl";

import { Alert, AlertDescription, AlertIcon } from "@/components/ui/alert";

/**
 * The notice every analytical page must show (PRD section 0, hard rules).
 * Add it to any page that presents market or portfolio analysis.
 */
export function Disclaimer() {
  const t = useTranslations("common");
  return (
    <Alert variant="warning" appearance="light" role="note">
      <AlertIcon>
        <Info />
      </AlertIcon>
      <AlertDescription>{t("disclaimer")}</AlertDescription>
    </Alert>
  );
}
