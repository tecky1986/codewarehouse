import type { ApiEnvelope } from "./types";
import { isOk } from "./types";

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const body = (await r.json()) as ApiEnvelope<T>;
  if (!isOk(body)) throw new Error(body.message || `code=${body.code}`);
  return body.data;
}

export const ALGORITHMS = [
  { key: "dblf", label: "DBLF" },
  { key: "maxspace", label: "最大空腔" },
  { key: "extreme_point", label: "极点" },
  { key: "wall_build", label: "砌墙" },
  { key: "guillotine", label: "切割" },
  { key: "freemix", label: "自由组合" },
];

// ---- tasks
export interface Task {
  id: number;
  name: string;
  created_at?: string;
  container_mode_json?: string | Record<string, unknown>;
  rules_json?: string | unknown[];
  site_groups_json?: string | Record<string, unknown>;
  adopted_plan_id?: number | null;
  status?: string;
}

export const Tasks = {
  list: () => req<Task[]>("/api/tasks"),
  get: (id: number) => req<Task>(`/api/tasks/${id}`),
  create: (name: string) =>
    req<Task>("/api/tasks", { method: "POST", body: JSON.stringify({ name }) }),
  update: (id: number, body: Record<string, unknown>) =>
    req<Task>(`/api/tasks/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  remove: (id: number) =>
    req<null>(`/api/tasks/${id}`, { method: "DELETE" }),
  compute: (id: number, body: { algorithms: string[] }) =>
    req<Job>(`/api/tasks/${id}/compute`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  plans: (id: number) => req<Plan[]>(`/api/tasks/${id}/plans`),
  adopt: (id: number, planId: number) =>
    req<{ adopted_plan_id: number }>(`/api/tasks/${id}/adopt-plan`, {
      method: "PUT",
      body: JSON.stringify({ plan_id: planId }),
    }),
  clearRuns: (id: number) =>
    req<null>(`/api/tasks/${id}/runs`, { method: "DELETE" }),
  importFile: async (id: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const r = await fetch(`/api/tasks/${id}/import`, { method: "POST", body: form });
    const body = (await r.json()) as ApiEnvelope<ImportPreview>;
    if (!isOk(body)) throw new Error(body.message);
    return body.data;
  },
  preview: (id: number) => req<ImportPreview>(`/api/tasks/${id}/import/preview`),
  pendingXlsxUrl: (id: number) => `/api/tasks/${id}/import/pending.xlsx`,
  batchMaintain: async (id: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const r = await fetch(`/api/tasks/${id}/import/batch-maintain`, {
      method: "POST",
      body: form,
    });
    const body = (await r.json()) as ApiEnvelope<Array<Record<string, unknown>>>;
    if (!isOk(body)) throw new Error(body.message);
    return body.data;
  },
  reMatch: (id: number) =>
    req<ImportPreview>(`/api/tasks/${id}/import/re-match`, { method: "POST" }),
  siteGroups: (id: number) => req<SiteGroup[]>(`/api/tasks/${id}/site-groups`),
  saveSiteGroups: (id: number, groups: SiteGroup[]) =>
    req<SiteGroup[]>(`/api/tasks/${id}/site-groups`, {
      method: "PUT",
      body: JSON.stringify(groups),
    }),
  sampleXlsxUrl: () => "/api/tasks/sample.xlsx",
};

// ---- jobs
export interface Job {
  id: number;
  task_id: number;
  status: "running" | "done" | "failed";
  algorithms: Array<{
    name: string;
    progress: number;
    eta_seconds: number;
    done_ms?: number;
    timed_out?: boolean;
  }>;
  progress?: Record<string, number>;
  eta_seconds?: Record<string, number>;
  error?: string | null;
  plan_ids?: number[];
  plans?: Plan[];
}

export const Jobs = {
  get: (id: number) => req<Job>(`/api/jobs/${id}`),
};

// ---- plans
export interface ContainerKpi {
  label: string;
  type_code: string;
  seq_no?: number;
  item_count: number;
  volume_used_m3: number;
  volume_capacity_m3: number;
  vol_util: number;
  payload_used_kg: number;
  payload_capacity_kg: number;
  pay_util: number;
  load_seq_correct_ratio?: number;
  constraint_ok_ratio?: number;
  cg_offset_mm?: number;
  freight_price?: number;
}

export interface OverallKpi {
  containers_used: number;
  vol_util: number;
  pay_util: number;
  completion: number;
  unassigned_count: number;
  unassigned_volume_m3: number;
  unassigned_weight_kg: number;
  load_seq_correct_ratio?: number;
  constraint_ok_ratio?: number;
  total_freight?: number;
  elapsed_s?: number;
  timed_out?: boolean;
}

export interface Plan {
  id: number;
  run_id: number;
  algorithm: string;
  is_adopted: number;
  container_count?: number;
  kpi: {
    per_container: ContainerKpi[];
    overall: OverallKpi;
  };
  created_ms: number;
  elapsed_s?: number;
}

export interface Placement {
  container_id: number | null;
  label: string | null;
  import_row_id: number | null;
  row_no: number | null;
  k_pn: string | null;
  g_packmatls: string | null;
  x: number;
  y: number;
  z: number;
  dim_x: number;
  dim_y: number;
  dim_z: number;
  rotation: number;
  load_seq: number | null;
  unassigned_reason: string | null;
}

export const Plans = {
  placements: (id: number) => req<Placement[]>(`/api/plans/${id}/placements`),
  exportUrl: (id: number, fmt: "xlsx" | "csv" = "xlsx") =>
    `/api/plans/${id}/export?fmt=${fmt}`,
};

// ---- import preview
export const IMPORT_COLUMNS = [
  { code: "A", key: "a_no", label: "编号" },
  { code: "B", key: "b_len", label: "长cm" },
  { code: "C", key: "c_wid", label: "宽cm" },
  { code: "D", key: "d_hgt", label: "高cm" },
  { code: "E", key: "e_cbm", label: "CBM" },
  { code: "F", key: "f_outcase", label: "OUTCASE" },
  { code: "G", key: "g_packmatls", label: "PackMatls" },
  { code: "H", key: "h_tare", label: "箱重kg" },
  { code: "I", key: "i_net", label: "净重kg" },
  { code: "J", key: "j_gross", label: "毛重kg" },
  { code: "K", key: "k_pn", label: "PN" },
  { code: "L", key: "l_note", label: "备注" },
  { code: "M", key: "m_site", label: "Site" },
  { code: "N", label: "箱号" },
  { code: "O", key: "o_ref", label: "REF" },
  { code: "P", key: "p_dn", label: "DN" },
  { code: "Q", key: "q_misc", label: "其他" },
] as const;

export interface ImportRow {
  id: number;
  task_id: number;
  row_no: number;
  a_no: string | null;
  b_len: number | null;
  c_wid: number | null;
  d_hgt: number | null;
  e_cbm: number | null;
  f_outcase: string | null;
  g_packmatls: string | null;
  h_tare: number | null;
  i_net: number | null;
  j_gross: number | null;
  k_pn: string | null;
  l_note: string | null;
  m_site: string | null;
  o_ref: string | null;
  p_dn: string | null;
  q_misc: string | null;
  filled_fields_json: string;
  source_flag: string;
  complete: boolean;
}

export interface ImportPreview {
  rows: ImportRow[];
  missing: Array<{ pn: string | null; packmatls: string | null; row_no: number | null }>;
  can_compute: boolean;
  row_count: number;
  distinct_sites?: string[];
  site_auto_confirmed?: boolean;
}

// ---- site groups
export interface SiteGroup {
  site: string;
  together: boolean;
  separate: boolean;
  items: Array<{
    row_no: number;
    outcase: string | null;
    packmatls: string | null;
    volume: number | null;
    gross: number | null;
  }>;
}

// ---- export templates
export interface ExportTemplate {
  id: number;
  name: string;
  is_default: number;
  columns_json: unknown;
}

export interface ExportColumn {
  field: string;
  header: string;
  width?: number;
  align?: string;
  format?: string;
}

export function templateColumns(t: ExportTemplate): ExportColumn[] {
  if (Array.isArray(t.columns_json)) return t.columns_json as ExportColumn[];
  return [];
}

export const ExportTemplates = {
  list: () => req<ExportTemplate[]>("/api/export-templates"),
  create: (name: string, columns: unknown, isDefault = false) =>
    req<ExportTemplate>("/api/export-templates", {
      method: "POST",
      body: JSON.stringify({
        name,
        columns_json: JSON.stringify(columns),
        is_default: isDefault ? 1 : 0,
      }),
    }),
  update: (id: number, body: Partial<{ name: string; columns: unknown; is_default: number }>) =>
    req<ExportTemplate>(`/api/export-templates/${id}`, {
      method: "PUT",
      body: JSON.stringify({
        name: body.name,
        ...(body.columns !== undefined
          ? { columns_json: JSON.stringify(body.columns) }
          : {}),
        ...(body.is_default !== undefined ? { is_default: body.is_default } : {}),
      }),
    }),
  remove: (id: number) =>
    req<null>(`/api/export-templates/${id}`, { method: "DELETE" }),
};

// ---- container types
export interface ContainerType {
  id: number;
  code: string;
  name: string;
  iso_code?: string | null;
  inner_l: number;
  inner_w: number;
  inner_h: number;
  door_w?: number | null;
  door_h?: number | null;
  max_payload: number;
  tare_weight?: number | null;
  volume?: number | null;
  freight_price?: number | null;
  enabled?: number;
  remark?: string | null;
}

export const ContainerTypes = {
  list: () => req<ContainerType[]>("/api/container-types"),
  create: (body: Partial<ContainerType>) =>
    req<ContainerType>("/api/container-types", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (id: number, body: Partial<ContainerType>) =>
    req<ContainerType>(`/api/container-types/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  remove: (id: number) =>
    req<null>(`/api/container-types/${id}`, { method: "DELETE" }),
};

// ---- packages
export interface PackageMaster {
  id: number;
  pn?: string | null;
  code?: string | null;
  name?: string | null;
  package_type?: string | null;
  cargo_type?: string | null;
  l: number | null;
  w: number | null;
  h: number | null;
  tare?: number | null;
  net?: number | null;
  gross?: number | null;
  rotatable?: number;
  crush_sensitive?: number;
  same_type_stack?: number;
  default_loading?: string | null;
  max_stack?: number | null;
  enabled?: number;
}

export const Packages = {
  list: () => req<PackageMaster[]>("/api/packages"),
  create: (body: Partial<PackageMaster>) =>
    req<PackageMaster>("/api/packages", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (id: number, body: Partial<PackageMaster>) =>
    req<PackageMaster>(`/api/packages/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  remove: (id: number) =>
    req<null>(`/api/packages/${id}`, { method: "DELETE" }),
  templateUrl: () => "/api/packages/template",
  exportUrl: () => "/api/packages/export",
  importFile: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const r = await fetch("/api/packages/import", { method: "POST", body: form });
    const body = (await r.json()) as ApiEnvelope<{
      saved: PackageMaster[];
      saved_count: number;
      skipped: number;
    }>;
    if (!isOk(body)) throw new Error(body.message);
    return body.data;
  },
};

export const Settings = {
  get: () => req<Record<string, string>>("/api/settings"),
  put: (body: Record<string, unknown>) =>
    req<Record<string, string>>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};
