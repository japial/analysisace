import { useTranslations } from "next-intl";

import { Field } from "@/components/form/form-parts";

import { CheckField } from "./forms";

/** FR25.9: questions to ask about a private deal. Answers are stored, never scored. */
export function DueDiligenceFields({
  checklist,
  answers,
}: {
  checklist: string[];
  answers?: Record<string, boolean | string> | null;
}) {
  const t = useTranslations("personal.assets");
  return (
    <fieldset className="flex flex-col gap-3 rounded-lg border border-border p-4">
      <legend className="px-1 text-sm font-medium text-mono">{t("ddTitle")}</legend>
      <p className="text-xs text-muted-foreground">{t("ddIntro")}</p>
      {checklist.map((item) => (
        <CheckField
          key={item}
          name={`dd_${item}`}
          label={t.has(`dd.${item}` as never) ? t(`dd.${item}` as never) : item}
          defaultChecked={answers?.[item] === true}
        />
      ))}
      <Field
        label={t("ddPromised")}
        name="dd_promised_return_pct"
        type="number"
        inputMode="decimal"
        step="0.01"
        defaultValue={typeof answers?.promised_return_pct === "string" ? answers.promised_return_pct : ""}
        hint={t("ddPromisedHint")}
      />
    </fieldset>
  );
}
