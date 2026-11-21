import { formatDate, formatNumber, type Role } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { UserControls } from "@/components/admin/user-controls";
import { Toolbar } from "@/components/layout/toolbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTable, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { listUsers } from "@/lib/api";
import { digitsFor } from "@/lib/locale";
import { requirePermission, requireToken } from "@/lib/session";

const PAGE_SIZE = 25;
const ROLES: Role[] = ["USER", "ANALYST", "ADMIN"];

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as Locale, namespace: "admin" });
  return { title: t("usersMetaTitle"), robots: { index: false } };
}

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

export default async function AdminUsersPage({ params, searchParams }: Props) {
  const { locale: rawLocale } = await params;
  const locale = rawLocale as Locale;
  setRequestLocale(locale);
  const me = await requirePermission(locale, "/admin/users", "USERS_MANAGE");

  const query = await searchParams;
  const q = first(query.q);
  const role = ROLES.find((r) => r === first(query.role));
  const page = Math.max(1, Number.parseInt(first(query.page), 10) || 1);

  const t = await getTranslations();
  const digits = digitsFor(locale);
  const users = await listUsers(await requireToken(), {
    q: q || undefined,
    role,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });
  const from = users.total === 0 ? 0 : users.offset + 1;
  const to = users.offset + users.items.length;

  const pageHref = (target: number) => ({
    pathname: "/admin/users",
    query: { ...(q && { q }), ...(role && { role }), ...(target > 1 && { page: String(target) }) },
  });

  return (
    <>
      <Toolbar
        title={t("admin.usersTitle")}
        description={t("admin.usersIntro")}
        breadcrumbs={[{ label: t("nav.home"), href: "/" }, { label: t("admin.usersTitle") }]}
      />
      <div className="container">
        <Card>
          <CardHeader className="py-3.5">
            <CardTitle>{t("admin.count", { count: users.total })}</CardTitle>
            {/* A GET form: filters live in the URL, so a filtered list can be bookmarked. */}
            <form className="flex flex-wrap items-center gap-2.5">
              <label htmlFor="user-search" className="sr-only">
                {t("admin.searchLabel")}
              </label>
              <Input
                id="user-search"
                type="search"
                name="q"
                defaultValue={q}
                maxLength={100}
                placeholder={t("admin.searchLabel")}
                className="w-56"
              />
              <label htmlFor="user-role" className="sr-only">
                {t("admin.role")}
              </label>
              <select
                id="user-role"
                name="role"
                defaultValue={role ?? ""}
                className="h-8.5 rounded-md border border-input bg-background px-3 text-2sm text-foreground"
              >
                <option value="">{t("admin.allRoles")}</option>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t(`roles.${r}.name`)}
                  </option>
                ))}
              </select>
              <Button type="submit" variant="outline">
                {t("admin.filter")}
              </Button>
            </form>
          </CardHeader>

          {users.items.length === 0 ? (
            <CardContent>
              <p className="text-sm text-muted-foreground">{t("admin.noUsers")}</p>
            </CardContent>
          ) : (
            <CardTable>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="min-w-44">{t("admin.user")}</TableHead>
                      <TableHead className="min-w-60">
                        {t("admin.role")} / {t("admin.active")}
                      </TableHead>
                      <TableHead className="min-w-32">{t("admin.joined")}</TableHead>
                      <TableHead className="min-w-44">{t("admin.lastSignIn")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.items.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-mono">{user.full_name}</span>
                            {user.id === me.id && (
                              <Badge variant="primary" appearance="light" size="sm">
                                {t("admin.you")}
                              </Badge>
                            )}
                            {!user.is_active && (
                              <Badge variant="destructive" appearance="light" size="sm">
                                {t("admin.inactive")}
                              </Badge>
                            )}
                          </div>
                          <div className="text-sm text-muted-foreground" lang="en">
                            {user.email}
                          </div>
                        </TableCell>
                        <TableCell>
                          <UserControls user={user} isSelf={user.id === me.id} />
                        </TableCell>
                        <TableCell>
                          {formatDate(user.created_at, { language: locale, digits })}
                        </TableCell>
                        <TableCell>
                          {user.last_login_at
                            ? formatDate(user.last_login_at, {
                                language: locale,
                                digits,
                                withTime: true,
                              })
                            : t("admin.never")}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardTable>
          )}

          {users.total > 0 && (
            <CardFooter className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
              <span>
                {t("admin.pageOf", {
                  from: formatNumber(from, { digits }),
                  to: formatNumber(to, { digits }),
                  total: formatNumber(users.total, { digits }),
                })}
              </span>
              <div className="flex gap-2">
                {page > 1 && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={pageHref(page - 1)}>{t("common.previous")}</Link>
                  </Button>
                )}
                {to < users.total && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={pageHref(page + 1)}>{t("common.next")}</Link>
                  </Button>
                )}
              </div>
            </CardFooter>
          )}
        </Card>
      </div>
    </>
  );
}
