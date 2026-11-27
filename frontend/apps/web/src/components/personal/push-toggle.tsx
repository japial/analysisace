"use client";

/**
 * Turns browser notifications on or off for this device (D26). The browser subscribes with
 * the server's public key; the subscription is saved through a server action, so the browser
 * never calls the API itself. Which alerts arrive is set per alert ("Push" or "Both").
 */
import { BellOff, BellRing } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState, useTransition } from "react";

import { removePushSubscriptionAction, savePushSubscriptionAction } from "@/app/actions/personal";
import { Button } from "@/components/ui/button";

type State = "checking" | "unsupported" | "blocked" | "off" | "on";

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = (base64url + "=".repeat((4 - (base64url.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  return (await navigator.serviceWorker.getRegistration("/")) ?? navigator.serviceWorker.register("/sw.js", { scope: "/" });
}

export function PushToggle({ publicKey }: { publicKey: string }) {
  const t = useTranslations("personal.push");
  const [state, setState] = useState<State>("checking");
  const [error, setError] = useState(false);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
        if (!cancelled) setState("unsupported");
        return;
      }
      if (Notification.permission === "denied") {
        if (!cancelled) setState("blocked");
        return;
      }
      const reg = await navigator.serviceWorker.getRegistration("/");
      const sub = reg ? await reg.pushManager.getSubscription() : null;
      if (!cancelled) setState(sub ? "on" : "off");
    })().catch(() => !cancelled && setState("unsupported"));
    return () => {
      cancelled = true;
    };
  }, []);

  const turnOn = () =>
    startTransition(async () => {
      setError(false);
      try {
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
          setState(permission === "denied" ? "blocked" : "off");
          return;
        }
        const reg = await registration();
        await navigator.serviceWorker.ready;
        const sub =
          (await reg.pushManager.getSubscription()) ??
          (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) }));
        const json = sub.toJSON();
        const result = await savePushSubscriptionAction({
          endpoint: json.endpoint ?? "",
          keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
        });
        if (result.error) {
          await sub.unsubscribe();
          setError(true);
          return;
        }
        setState("on");
      } catch {
        setError(true);
      }
    });

  const turnOff = () =>
    startTransition(async () => {
      setError(false);
      try {
        const reg = await navigator.serviceWorker.getRegistration("/");
        const sub = reg ? await reg.pushManager.getSubscription() : null;
        if (sub) {
          await removePushSubscriptionAction(sub.endpoint);
          await sub.unsubscribe();
        }
        setState("off");
      } catch {
        setError(true);
      }
    });

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-secondary-foreground" aria-live="polite">
        {state === "checking" ? t("checking") : t(`state.${state}`)}
      </p>
      {state === "off" && (
        <Button onClick={turnOn} disabled={pending} className="self-start">
          <BellRing />
          {t("turnOn")}
        </Button>
      )}
      {state === "on" && (
        <Button variant="outline" onClick={turnOff} disabled={pending} className="self-start">
          <BellOff />
          {t("turnOff")}
        </Button>
      )}
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {t("failed")}
        </p>
      )}
    </div>
  );
}
