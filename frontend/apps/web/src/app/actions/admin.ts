"use server";

import type { Role } from "@analysisace/core";
import { revalidatePath } from "next/cache";

import * as api from "@/lib/api";
import { type FormState, toFormError } from "@/lib/form-state";
import { requireToken } from "@/lib/session";

const ROLES: readonly Role[] = ["USER", "ANALYST", "ADMIN"];

/**
 * Changes a user's role or access. The API enforces the USERS_MANAGE permission and the
 * safety rules (no self-change, never remove the last admin); this only forwards the call.
 */
export async function updateUserAction(
  userId: string,
  change: { role?: string; isActive?: boolean },
): Promise<FormState> {
  const role = ROLES.find((r) => r === change.role);
  if (change.role !== undefined && !role) return { error: "VALIDATION" };
  try {
    await api.updateUser(await requireToken(), userId, { role, is_active: change.isActive });
  } catch (error) {
    return toFormError(error);
  }
  revalidatePath("/", "layout");
  return { ok: true };
}
