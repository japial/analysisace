import { FileDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { downloadHref } from "@/lib/download";

/**
 * Downloads a statement as a PDF made by the API (F13), in the page language. The PDF
 * repeats the stored figures with the disclaimer, computation time and sources.
 */
export function PdfButton({ locale, apiPath, label }: { locale: string; apiPath: string; label: string }) {
  const lang = locale === "bn" ? "bn" : "en";
  return (
    <Button variant="outline" size="sm" asChild>
      <a href={downloadHref(locale, `${apiPath}?locale=${lang}`)} download>
        <FileDown />
        {label}
      </a>
    </Button>
  );
}
