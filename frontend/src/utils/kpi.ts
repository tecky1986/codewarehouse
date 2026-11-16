import type { Plan } from "@/api";

export function pct(v: number | undefined | null): string {
  if (v == null) return "—";
  return (v * 100).toFixed(1) + "%";
}

export function errorCodesText(codes?: Record<string, number> | null): string {
  if (!codes) return "";
  return Object.entries(codes)
    .map(([k, n]) => (n > 1 ? `${k}×${n}` : k))
    .join(" ");
}

export function verifyText(p: Plan): string {
  const o = p.kpi.overall;
  if (o.verify_ok == null) return "—";
  if (o.verify_ok) return "通过";
  return errorCodesText(o.verify_error_codes) || "未通过";
}
