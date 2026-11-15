"use client";

import type { Role, User } from "@analysisace/core";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { updateUserAction } from "@/app/actions/admin";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { ErrorCode } from "@/lib/form-state";

const ROLES: Role[] = ["USER", "ANALYST", "ADMIN"];

interface Props {
  user: User;
  /** An admin cannot change their own role or access; the API refuses it too. */
  isSelf: boolean;
}

/** Role picker and access switch for one row of the users table. */
export function UserControls({ user, isSelf }: Props) {
  const t = useTranslations();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<ErrorCode | null>(null);
  // Bumped after a refused change, so the controls snap back to the saved values.
  const [resetKey, setResetKey] = useState(0);

  function apply(change: { role?: string; isActive?: boolean }) {
    setError(null);
    startTransition(async () => {
      const result = await updateUserAction(user.id, change);
      if (result.error) {
        setError(result.error);
        setResetKey((key) => key + 1);
      }
    });
  }

  const disabled = isSelf || pending;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-3" key={`${user.role}-${user.is_active}-${resetKey}`}>
        <Select defaultValue={user.role} disabled={disabled} onValueChange={(role) => apply({ role })}>
          <SelectTrigger
            size="sm"
            className="w-36"
            aria-label={t("admin.roleFor", { name: user.full_name })}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((role) => (
              <SelectItem key={role} value={role}>
                {t(`roles.${role}.name`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Switch
          size="sm"
          defaultChecked={user.is_active}
          disabled={disabled}
          onCheckedChange={(isActive) => apply({ isActive })}
          aria-label={t("admin.activeFor", { name: user.full_name })}
        />
      </div>
      {error && (
        <p role="alert" className="max-w-64 text-xs text-destructive">
          {t(`errors.${error}`)}
        </p>
      )}
    </div>
  );
}
