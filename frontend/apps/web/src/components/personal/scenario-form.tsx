"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Field } from "@/components/form/form-parts";
import type { FormState } from "@/lib/form-state";

import { ActionForm, FieldGrid, type Option, SelectField } from "./forms";

interface Props {
  action: (state: FormState, form: FormData) => Promise<FormState>;
  presets: Option[];
  events: Option[];
}

/** Picks a what-if (FR18.1) and the one number or event it needs. */
export function ScenarioForm({ action, presets, events }: Props) {
  const t = useTranslations("personal.fire");
  const [preset, setPreset] = useState(presets[0]?.value ?? "MARKET_CRASH");
  return (
    <ActionForm action={action} submitLabel={t("runScenario")} success={t("scenarioDone")}>
      <FieldGrid>
        <SelectField label={t("scenario")} name="preset" options={presets} defaultValue={preset} onValueChange={setPreset} />
        {preset === "EVENT_REPLAY" ? (
          events.length > 0 ? (
            <SelectField label={t("event")} name="event_id" options={events} hint={t("eventHint")} />
          ) : (
            <p className="self-end text-sm text-muted-foreground">{t("noEvents")}</p>
          )
        ) : (
          <Field
            key={preset}
            label={t(`param.${preset}` as "param.MARKET_CRASH")}
            name="value"
            type="number"
            inputMode="decimal"
            min="0"
            step="0.1"
            // Left empty, the API uses the size set in config/personal.yaml.
            hint={t("paramHint")}
          />
        )}
      </FieldGrid>
    </ActionForm>
  );
}
