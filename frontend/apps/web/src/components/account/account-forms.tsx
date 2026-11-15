"use client";

import type { OptionalConsent, User } from "@analysisace/core";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import {
  changePasswordAction,
  deleteAccountAction,
  updateConsentsAction,
  updateProfileAction,
} from "@/app/actions/account";
import { Field, FormMessage, SubmitButton } from "@/components/form/form-parts";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { INITIAL_FORM_STATE } from "@/lib/form-state";

const PASSWORD_MIN = 8;
const PASSWORD_MAX = 128;
const CONSENTS: OptionalConsent[] = ["RELIGIOUS_PREFERENCES", "COMMUNITY_BENCHMARKING", "MARKETING"];

export function ProfileForm({ user }: { user: User }) {
  const t = useTranslations();
  const [state, action] = useActionState(updateProfileAction, INITIAL_FORM_STATE);

  return (
    <form action={action} className="flex max-w-md flex-col gap-4">
      <FormMessage state={state} success={t("common.saved")} />
      <Field
        label={t("auth.fullName")}
        name="full_name"
        defaultValue={user.full_name}
        autoComplete="name"
        maxLength={120}
        required
      />
      <Field label={t("auth.email")} name="email" value={user.email} readOnly disabled lang="en" />
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="locale">{t("auth.preferredLanguage")}</Label>
        <Select name="locale" defaultValue={user.locale}>
          <SelectTrigger id="locale">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="bn">বাংলা</SelectItem>
            <SelectItem value="en">English</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <SubmitButton className="self-start">{t("common.save")}</SubmitButton>
    </form>
  );
}

export function PasswordForm() {
  const t = useTranslations();
  const [state, action] = useActionState(changePasswordAction, INITIAL_FORM_STATE);

  return (
    // The key clears both fields after a successful change.
    <form action={action} key={state.ok ? "done" : "form"} className="flex max-w-md flex-col gap-4">
      <FormMessage state={state} success={t("account.passwordChanged")} />
      <Field
        label={t("account.currentPassword")}
        name="current_password"
        type="password"
        autoComplete="current-password"
        required
      />
      <Field
        label={t("auth.newPassword")}
        name="new_password"
        type="password"
        autoComplete="new-password"
        minLength={PASSWORD_MIN}
        maxLength={PASSWORD_MAX}
        hint={t("auth.passwordHint")}
        required
      />
      <SubmitButton className="self-start">{t("account.changePassword")}</SubmitButton>
    </form>
  );
}

/** Optional consents (FR23.1, FR23.2). Each can be withdrawn as easily as it was given. */
export function ConsentsForm({ user }: { user: User }) {
  const t = useTranslations();
  const [state, action] = useActionState(updateConsentsAction, INITIAL_FORM_STATE);

  return (
    <form action={action} className="flex flex-col gap-5">
      <FormMessage state={state} success={t("common.saved")} />
      {CONSENTS.map((purpose) => (
        <div key={purpose} className="flex items-start justify-between gap-4">
          <div>
            <Label htmlFor={purpose} className="text-sm font-medium text-mono">
              {t(`account.consents.${purpose}.title`)}
            </Label>
            <p id={`${purpose}-body`} className="mt-0.5 max-w-xl text-sm text-muted-foreground">
              {t(`account.consents.${purpose}.body`)}
            </p>
          </div>
          <Switch
            id={purpose}
            name={purpose}
            defaultChecked={user.consents[purpose]?.granted ?? false}
            aria-describedby={`${purpose}-body`}
          />
        </div>
      ))}
      <SubmitButton className="self-start">{t("common.save")}</SubmitButton>
    </form>
  );
}

/** Account deletion (FR23.4). Asks for the password inside a confirmation dialog. */
export function DeleteAccount() {
  const t = useTranslations();
  const [state, action] = useActionState(deleteAccountAction, INITIAL_FORM_STATE);

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive">{t("account.deleteButton")}</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <form action={action} className="flex flex-col gap-4">
          <AlertDialogHeader>
            <AlertDialogTitle>{t("account.deleteConfirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("account.deleteConfirmBody")}</AlertDialogDescription>
          </AlertDialogHeader>
          <FormMessage state={state} />
          <Field
            label={t("auth.password")}
            name="password"
            id="delete-password"
            type="password"
            autoComplete="current-password"
            required
          />
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <SubmitButton variant="destructive">{t("account.deleteConfirm")}</SubmitButton>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  );
}
