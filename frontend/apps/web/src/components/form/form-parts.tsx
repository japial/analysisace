"use client";

import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ComponentProps, type ReactNode, useId } from "react";
import { useFormStatus } from "react-dom";

import { Alert, AlertDescription, AlertIcon } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { FormState } from "@/lib/form-state";

interface FieldProps extends ComponentProps<typeof Input> {
  label: string;
  name: string;
  hint?: string;
  /** Shown beside the label, for example a "Forgot password?" link. */
  aside?: ReactNode;
}

/**
 * A labelled input. The hint is tied to the input for screen readers. Without an explicit
 * `id`, each field gets a unique one, so two forms on a page with the same field name
 * never share an id (and a label never points at the other form's input).
 */
export function Field({ label, name, hint, aside, id: givenId, ...props }: FieldProps) {
  const autoId = useId();
  const id = givenId ?? autoId;
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={id}>{label}</Label>
        {aside}
      </div>
      <Input id={id} name={name} aria-describedby={hintId} {...props} />
      {hint && (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}

/** Submit button that disables itself and shows a spinner while the form is sending. */
export function SubmitButton({ children, ...props }: ComponentProps<typeof Button>) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending} aria-busy={pending} {...props}>
      {pending && <LoaderCircle className="animate-spin" />}
      {children}
    </Button>
  );
}

/** The error from a server action, or a success message when `success` is given. */
export function FormMessage({ state, success }: { state: FormState; success?: string }) {
  const t = useTranslations("errors");
  if (state.error) {
    return (
      <Alert variant="destructive" appearance="light" role="alert">
        <AlertIcon>
          <CircleAlert />
        </AlertIcon>
        <AlertDescription>{t(state.error)}</AlertDescription>
      </Alert>
    );
  }
  if (state.ok && success) {
    return (
      <Alert variant="success" appearance="light" role="status">
        <AlertIcon>
          <CircleCheck />
        </AlertIcon>
        <AlertDescription>{success}</AlertDescription>
      </Alert>
    );
  }
  return null;
}
