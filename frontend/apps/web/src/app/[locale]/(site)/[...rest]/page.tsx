import { notFound } from "next/navigation";

// Sends any unknown path under a locale to the translated not-found page.
export default function CatchAll() {
  notFound();
}
