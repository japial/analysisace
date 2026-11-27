/**
 * Shown under the menu while the signed-in person's email is unconfirmed (D25), or after
 * email to it bounced (D35): alert and report emails wait either way. The person can ask for
 * a new link, and opening it resumes them; nothing else is blocked.
 */
import type { User } from "@analysisace/core";
import { MailWarning } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { resendVerificationAction } from "@/app/actions/auth";
import { ActionButton } from "@/components/personal/forms";

export async function VerifyEmailBanner({ user }: { user: User | null }) {
  const bounced = Boolean(user?.email_bounced_at);
  if (!user || (user.email_verified_at && !bounced)) return null;
  const t = await getTranslations("auth");
  return (
    <section aria-label={t("verifyTitle")} className="border-b border-border bg-muted text-mono" data-print="hide">
      <div className="container flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2.5 text-sm">
        <p className="flex items-center gap-2">
          <MailWarning className="size-4 shrink-0 text-primary" aria-hidden="true" />
          <span>{t(bounced ? "bounceBanner" : "verifyBanner", { email: user.email })}</span>
        </p>
        <ActionButton action={resendVerificationAction} variant="outline">
          {t("verifyResend")}
        </ActionButton>
      </div>
    </section>
  );
}
