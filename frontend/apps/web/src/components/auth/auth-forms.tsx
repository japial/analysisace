"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import {
  confirmPasswordResetAction,
  requestPasswordResetAction,
  signInAction,
  signUpAction,
} from "@/app/actions/auth";
import { Field, FormMessage, SubmitButton } from "@/components/form/form-parts";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";
import { INITIAL_FORM_STATE } from "@/lib/form-state";

const PASSWORD_MIN = 8;
const PASSWORD_MAX = 128;

function Heading({ title, intro }: { title: string; intro: string }) {
  return (
    <div className="mb-5 text-center">
      <h1 className="text-lg font-semibold text-mono">{title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{intro}</p>
    </div>
  );
}

function linkQuery(next: string) {
  return next === "/" ? undefined : { next };
}

export function SignInForm({ next }: { next: string }) {
  const t = useTranslations("auth");
  const [state, action] = useActionState(signInAction, INITIAL_FORM_STATE);

  return (
    <form action={action} className="flex flex-col gap-4">
      <Heading title={t("signInTitle")} intro={t("signInIntro")} />
      <FormMessage state={state} />
      <input type="hidden" name="next" value={next} />
      <Field label={t("email")} name="email" type="email" autoComplete="email" required />
      <Field
        label={t("password")}
        name="password"
        type="password"
        autoComplete="current-password"
        required
        aside={
          <Link href="/forgot-password" className="text-sm text-primary hover:underline">
            {t("forgotLink")}
          </Link>
        }
      />
      <SubmitButton>{t("signInSubmit")}</SubmitButton>
      <p className="text-center text-sm text-muted-foreground">
        {t("noAccount")}{" "}
        <Link
          href={{ pathname: "/signup", query: linkQuery(next) }}
          className="font-medium text-primary hover:underline"
        >
          {t("signUpSubmit")}
        </Link>
      </p>
    </form>
  );
}

export function SignUpForm({ next }: { next: string }) {
  const t = useTranslations("auth");
  const [state, action] = useActionState(signUpAction, INITIAL_FORM_STATE);

  return (
    <form action={action} className="flex flex-col gap-4">
      <Heading title={t("signUpTitle")} intro={t("signUpIntro")} />
      <FormMessage state={state} />
      <input type="hidden" name="next" value={next} />
      <Field label={t("fullName")} name="full_name" autoComplete="name" maxLength={120} required />
      <Field label={t("email")} name="email" type="email" autoComplete="email" required />
      <Field
        label={t("password")}
        name="password"
        type="password"
        autoComplete="new-password"
        minLength={PASSWORD_MIN}
        maxLength={PASSWORD_MAX}
        hint={t("passwordHint")}
        required
      />
      {/* FR23.1: consent is an explicit, unticked choice. */}
      <div className="flex items-start gap-2.5">
        <Checkbox id="accept_terms" name="accept_terms" required className="mt-0.5" />
        <Label htmlFor="accept_terms" className="text-sm font-normal leading-normal">
          {t("acceptTerms")}
        </Label>
      </div>
      <SubmitButton>{t("signUpSubmit")}</SubmitButton>
      <p className="text-center text-sm text-muted-foreground">
        {t("haveAccount")}{" "}
        <Link
          href={{ pathname: "/signin", query: linkQuery(next) }}
          className="font-medium text-primary hover:underline"
        >
          {t("signInSubmit")}
        </Link>
      </p>
    </form>
  );
}

export function ForgotPasswordForm() {
  const t = useTranslations("auth");
  const [state, action] = useActionState(requestPasswordResetAction, INITIAL_FORM_STATE);

  return (
    <form action={action} className="flex flex-col gap-4">
      <Heading title={t("forgotTitle")} intro={t("forgotIntro")} />
      <FormMessage state={state} success={t("forgotSent")} />
      {!state.ok && (
        <>
          <Field label={t("email")} name="email" type="email" autoComplete="email" required />
          <SubmitButton>{t("forgotSubmit")}</SubmitButton>
        </>
      )}
      <Link href="/signin" className="text-center text-sm font-medium text-primary hover:underline">
        {t("backToSignIn")}
      </Link>
    </form>
  );
}

export function ResetPasswordForm({ token }: { token: string }) {
  const t = useTranslations("auth");
  const [state, action] = useActionState(confirmPasswordResetAction, INITIAL_FORM_STATE);
  const needsNewLink = !token || state.error === "INVALID_TOKEN";

  return (
    <form action={action} className="flex flex-col gap-4">
      <Heading title={t("resetTitle")} intro={t("resetIntro")} />
      <FormMessage
        state={token ? state : { error: "INVALID_TOKEN" }}
        success={t("resetDone")}
      />
      {token && !state.ok && (
        <>
          <input type="hidden" name="token" value={token} />
          <Field
            label={t("newPassword")}
            name="new_password"
            type="password"
            autoComplete="new-password"
            minLength={PASSWORD_MIN}
            maxLength={PASSWORD_MAX}
            hint={t("passwordHint")}
            required
          />
          <SubmitButton>{t("resetSubmit")}</SubmitButton>
        </>
      )}
      <Link
        href={needsNewLink ? "/forgot-password" : "/signin"}
        className="text-center text-sm font-medium text-primary hover:underline"
      >
        {needsNewLink ? t("requestNewLink") : t("backToSignIn")}
      </Link>
    </form>
  );
}
