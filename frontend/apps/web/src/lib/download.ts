/** Link to a file download passed through `/personal/download` (see that route). */
export function downloadHref(locale: string, apiPath: string): string {
  return `/${locale}/personal/download?path=${encodeURIComponent(apiPath)}`;
}
