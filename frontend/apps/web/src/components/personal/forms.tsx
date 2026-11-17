"use client";

/**
 * Small form kit for the personal finance pages. Server components pass in a bound server
 * action; these components handle the pending state, the error or success message and,
 * after a successful save, clearing the form.
 */
import { Plus, Trash2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  type ComponentProps,
  type ReactNode,
  useActionState,
  useId,
  useState,
  useTransition,
} from "react";

import { FormMessage, SubmitButton } from "@/components/form/form-parts";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Input, inputVariants } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { type ErrorCode, type FormState, INITIAL_FORM_STATE } from "@/lib/form-state";
import { cn } from "@/lib/utils";

type FormAction = (state: FormState, form: FormData) => Promise<FormState>;

interface ActionFormProps {
  action: FormAction;
  submitLabel: string;
  /** Shown after a successful save. */
  success?: string;
  children: ReactNode;
  className?: string;
  /** Clear the fields after a successful save (default). Off for edit forms. */
  reset?: boolean;
}

/** A form posting to a server action, with its message and submit button. */
export function ActionForm({
  action,
  submitLabel,
  success,
  children,
  className,
  reset = true,
}: ActionFormProps) {
  const t = useTranslations("personal");
  const [state, formAction] = useActionState(action, INITIAL_FORM_STATE);
  const [saves, setSaves] = useState(0);
  const [lastState, setLastState] = useState(state);
  // Count successful saves so the fields can be remounted (cleared) after each one.
  if (state !== lastState) {
    setLastState(state);
    if (state.ok) setSaves((n) => n + 1);
  }

  return (
    <form action={formAction} className={cn("flex flex-col gap-4", className)}>
      <FormMessage state={state} success={success} />
      {state.imported && (
        <div role="status" className="text-sm text-secondary-foreground">
          <p>
            {t("import.result", {
              imported: state.imported.imported,
              updated: state.imported.updated,
            })}
          </p>
          {state.imported.errors.length > 0 && (
            <ul className="mt-1 list-disc ps-5 text-destructive">
              {state.imported.errors.slice(0, 20).map((row, index) => (
                <li key={index}>
                  {t("import.rowError", { row: String(row.row ?? "?"), error: String(row.error ?? "") })}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <div key={reset ? saves : 0} className="contents">
        {children}
      </div>
      <SubmitButton className="self-start">{submitLabel}</SubmitButton>
    </form>
  );
}

/** Lays fields out in one column on phones and up to three on wide screens. */
export function FieldGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {children}
    </div>
  );
}

export interface Option {
  value: string;
  label: string;
}

interface SelectFieldProps {
  label: string;
  name: string;
  options: Option[];
  defaultValue?: string;
  required?: boolean;
  hint?: string;
  /** Lets the person leave the choice empty. */
  placeholder?: string;
  onValueChange?: (value: string) => void;
  className?: string;
}

const NONE = "__none__";

/** A labelled select that posts its value with the form. */
export function SelectField({
  label,
  name,
  options,
  defaultValue,
  required,
  hint,
  placeholder,
  onValueChange,
  className,
}: SelectFieldProps) {
  const id = useId();
  const [value, setValue] = useState(defaultValue ?? (placeholder ? NONE : options[0]?.value));
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      <Select
        value={value}
        onValueChange={(next) => {
          setValue(next);
          onValueChange?.(next === NONE ? "" : next);
        }}
        required={required}
      >
        <SelectTrigger id={id} aria-describedby={hint ? `${id}-hint` : undefined}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {placeholder && <SelectItem value={NONE}>{placeholder}</SelectItem>}
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <input type="hidden" name={name} value={value === NONE ? "" : (value ?? "")} />
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}

/** A labelled multi-line text box. */
export function TextareaField({
  label,
  name,
  hint,
  className,
  ...props
}: ComponentProps<"textarea"> & { label: string; name: string; hint?: string }) {
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      <textarea
        id={id}
        name={name}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className={cn(inputVariants(), "h-auto min-h-24 py-2 font-mono text-xs")}
        {...props}
      />
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}

/** A labelled tick box. Posts "on" when ticked. */
export function CheckField({
  label,
  name,
  defaultChecked,
  hint,
}: {
  label: string;
  name: string;
  defaultChecked?: boolean;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="flex items-start gap-2.5">
      <Checkbox
        id={id}
        name={name}
        defaultChecked={defaultChecked}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="mt-0.5"
      />
      <div>
        <Label htmlFor={id}>{label}</Label>
        {hint && (
          <p id={`${id}-hint`} className="text-xs text-muted-foreground">
            {hint}
          </p>
        )}
      </div>
    </div>
  );
}

/** A labelled file picker. */
export function FileField({
  label,
  name,
  accept,
  hint,
  required,
}: {
  label: string;
  name: string;
  accept?: string;
  hint?: string;
  required?: boolean;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        name={name}
        type="file"
        accept={accept}
        required={required}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="file:me-3 file:border-0 file:bg-transparent file:text-sm file:font-medium"
      />
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}

/** A button that runs one action straight away, with an inline error if it is refused. */
export function ActionButton({
  action,
  children,
  variant = "outline",
  size = "sm",
  className,
}: {
  action: () => Promise<FormState>;
  children: ReactNode;
  variant?: ComponentProps<typeof Button>["variant"];
  size?: ComponentProps<typeof Button>["size"];
  className?: string;
}) {
  const t = useTranslations("errors");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<ErrorCode | null>(null);
  return (
    <span className={cn("inline-flex flex-col gap-1", className)}>
      <Button
        type="button"
        variant={variant}
        size={size}
        disabled={pending}
        aria-busy={pending}
        onClick={() =>
          startTransition(async () => {
            const result = await action();
            setError(result?.error ?? null);
          })
        }
      >
        {children}
      </Button>
      {error && (
        <span role="alert" className="text-xs text-destructive">
          {t(error)}
        </span>
      )}
    </span>
  );
}

/** A switch that saves as soon as it is flipped. */
export function ToggleSwitch({
  action,
  checked,
  label,
}: {
  action: (value: boolean) => Promise<FormState>;
  checked: boolean;
  label: string;
}) {
  const t = useTranslations("errors");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<ErrorCode | null>(null);
  const [resetKey, setResetKey] = useState(0);
  return (
    <span className="inline-flex flex-col gap-1">
      <Switch
        key={resetKey}
        size="sm"
        defaultChecked={checked}
        disabled={pending}
        aria-label={label}
        onCheckedChange={(value) =>
          startTransition(async () => {
            const result = await action(value);
            if (result?.error) {
              setError(result.error);
              setResetKey((n) => n + 1);
            } else setError(null);
          })
        }
      />
      {error && (
        <span role="alert" className="text-xs text-destructive">
          {t(error)}
        </span>
      )}
    </span>
  );
}

/** A delete button that asks first. */
export function DeleteButton({
  action,
  label,
  title,
  body,
  iconOnly = true,
}: {
  action: () => Promise<FormState>;
  /** Names the thing, for screen readers and the button text. */
  label: string;
  title: string;
  body?: string;
  iconOnly?: boolean;
}) {
  const t = useTranslations();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<ErrorCode | null>(null);
  const [open, setOpen] = useState(false);
  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild>
        <Button
          variant={iconOnly ? "ghost" : "destructive"}
          appearance={iconOnly ? undefined : "default"}
          size="sm"
          mode={iconOnly ? "icon" : undefined}
          aria-label={label}
          title={label}
        >
          <Trash2 />
          {!iconOnly && label}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{body ?? t("personal.deleteBody")}</AlertDialogDescription>
        </AlertDialogHeader>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {t(`errors.${error}`)}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
          <Button
            variant="destructive"
            disabled={pending}
            aria-busy={pending}
            onClick={() =>
              startTransition(async () => {
                const result = await action();
                if (result?.error) setError(result.error);
                else setOpen(false);
              })
            }
          >
            {t("personal.delete")}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

interface OwnerRow {
  member: string;
  external: string;
  pct: string;
}

/**
 * Who owns an asset and in what share (FR24.3). Posts parallel `owner_member`,
 * `owner_external` and `owner_pct` fields. Leave it untouched for "the person adding it".
 */
export function OwnersEditor({
  members,
  initial = [],
}: {
  members: Option[];
  initial?: OwnerRow[];
}) {
  const t = useTranslations("personal.owners");
  const [rows, setRows] = useState<OwnerRow[]>(initial);
  const update = (index: number, change: Partial<OwnerRow>) =>
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...change } : row)));

  return (
    <fieldset className="flex flex-col gap-3 rounded-lg border border-border p-4">
      <legend className="px-1 text-sm font-medium text-mono">{t("title")}</legend>
      <p className="text-xs text-muted-foreground">{t("hint")}</p>
      {rows.map((row, index) => (
        <div key={index} className="flex flex-wrap items-end gap-3">
          <SelectField
            label={t("owner")}
            name="owner_member"
            options={[...members, { value: "EXTERNAL", label: t("external") }]}
            defaultValue={row.member}
            onValueChange={(member) => update(index, { member })}
            className="w-48"
          />
          {row.member === "EXTERNAL" && (
            <div className="flex w-44 flex-col gap-1.5">
              <Label htmlFor={`owner-ext-${index}`}>{t("externalName")}</Label>
              <Input
                id={`owner-ext-${index}`}
                name="owner_external"
                defaultValue={row.external}
                maxLength={120}
                required
              />
            </div>
          )}
          {row.member !== "EXTERNAL" && <input type="hidden" name="owner_external" value="" />}
          <div className="flex w-28 flex-col gap-1.5">
            <Label htmlFor={`owner-pct-${index}`}>{t("pct")}</Label>
            <Input
              id={`owner-pct-${index}`}
              name="owner_pct"
              type="number"
              inputMode="decimal"
              min="0.01"
              max="100"
              step="0.01"
              defaultValue={row.pct}
              required
            />
          </div>
          <Button
            type="button"
            variant="ghost"
            mode="icon"
            size="sm"
            aria-label={t("remove")}
            onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
          >
            <X />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() =>
          setRows((current) => [...current, { member: members[0]?.value ?? "EXTERNAL", external: "", pct: "" }])
        }
      >
        <Plus />
        {t("add")}
      </Button>
    </fieldset>
  );
}
