"use client";

/**
 * Creates a firm API key (FR9.2) and shows it once. Only its hash is stored, so the box
 * says plainly that it cannot be shown again.
 */
import { KeyRound } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { type KeyFormState, createApiKeyAction } from "@/app/actions/firm";
import { Field, FormMessage, SubmitButton } from "@/components/form/form-parts";

export function ApiKeyForm({ firmId }: { firmId: string }) {
  const t = useTranslations("firm");
  const [state, action] = useActionState(createApiKeyAction.bind(null, firmId), {} as KeyFormState);

  return (
    <form action={action} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-60 grow">
          <Field label={t("keyName")} name="name" maxLength={120} placeholder={t("keyNamePlaceholder")} required />
        </div>
        <SubmitButton>
          <KeyRound />
          {t("createKey")}
        </SubmitButton>
      </div>
      {state.error && <FormMessage state={state} />}
      {state.ok && state.key && (
        <div className="flex flex-col gap-1.5 rounded-lg border border-primary/40 bg-primary/5 p-3 text-sm">
          <p className="font-medium text-mono">{t("keyOnce")}</p>
          <code className="block break-all rounded bg-background px-2 py-1.5 font-mono text-xs select-all" lang="en">
            {state.key}
          </code>
        </div>
      )}
    </form>
  );
}
