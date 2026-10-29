import type {
  AuthProvider,
  BaseRecord,
  CreateParams,
  DataProvider,
  GetListParams,
  GetOneParams,
  UpdateParams,
} from "@refinedev/core";
import { api, baseUrl, request } from "./client";
import { session } from "../auth/session";
import type { Page, TableQuery } from "./types";

export function tablePath(resource: string): string {
  if (
    !/^(drivers|handoffs|accountants|drivers\/[a-f0-9-]{36}\/(income|expenses|receipts|mileage|documents|messages|notes|activity))$/.test(
      resource,
    )
  ) {
    throw new Error("Unsupported table resource");
  }
  return `/staff/${resource}/search`;
}

export const dataProvider: DataProvider = {
  getApiUrl: () => baseUrl,
  getList: async <TData extends BaseRecord>({
    resource,
    meta,
  }: GetListParams) => {
    const query = meta?.query as TableQuery;
    if (!query) throw new Error("A server table query is required");
    const page = await request<Page<TData>>(tablePath(resource), {
      method: "POST",
      body: query,
      signal: meta?.signal,
    });
    return { data: page.items, total: page.total };
  },
  getOne: async <TData extends BaseRecord>({
    resource,
    id,
    meta,
  }: GetOneParams) => {
    if (resource !== "drivers" || typeof meta?.tax_year !== "string")
      throw new Error("Driver details require a selected tax year");
    return {
      data: await request<TData>(`/staff/drivers/${id}/overview`, {
        method: "POST",
        body: { tax_year: meta.tax_year },
      }),
    };
  },
  create: async <TData extends BaseRecord, TVariables>({
    resource,
    variables,
  }: CreateParams<TVariables>) => ({
    data: await api.mutate<TData>(`/${resource}`, variables),
  }),
  update: async <TData extends BaseRecord, TVariables>({
    resource,
    id,
    variables,
  }: UpdateParams<TVariables>) => ({
    data: await api.mutate<TData>(`/${resource}/${id}`, variables, "PATCH"),
  }),
  deleteOne: async () => {
    throw new Error(
      "Financial deletion is unavailable. Use the documented reversal workflow.",
    );
  },
};

export const authProvider: AuthProvider = {
  login: async ({ email, password }: { email: string; password: string }) => {
    try {
      const result = await api.login(email, password);
      session.start(result);
      return { success: true, redirectTo: "/" };
    } catch (error) {
      return { success: false, error: error as Error };
    }
  },
  logout: async () => {
    try {
      await api.logout();
    } finally {
      session.end();
    }
    return { success: true, redirectTo: "/login" };
  },
  check: async () => ({
    authenticated: Boolean(session.token()),
    ...(!session.token() ? { redirectTo: "/login" } : {}),
  }),
  getIdentity: async () => session.get()?.staff,
  getPermissions: async () => session.get()?.staff.role,
  onError: async (error) => ({ logout: error?.statusCode === 401, error }),
};
