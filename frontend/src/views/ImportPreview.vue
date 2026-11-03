<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute } from "vue-router";
import {
  Tasks,
  ContainerTypes,
  IMPORT_COLUMNS,
  type ImportPreview,
  type ImportRow,
  type ContainerType,
} from "@/api";
import StepNav from "@/components/StepNav.vue";

const route = useRoute();
const tid = ref(Number(route.params.id));

const preview = ref<ImportPreview | null>(null);
const types = ref<ContainerType[]>([]);
const importing = ref(false);
const error = ref("");
const modeSaved = ref(false);
const modeError = ref("");
const fileInput = ref<HTMLInputElement>();
const pendingInput = ref<HTMLInputElement>();
const hasMode = ref(false);
const showGuide = ref(true);

// mode: "fixed" | "freemix"
const mode = ref<"fixed" | "freemix">("fixed");
// fixed: single type + upper limit (max qty)
const fixedType = ref("");
const fixedMaxQty = ref(0);
// freemix: type lock + qty lock + max
const freemixTypeLock = ref<Record<string, boolean>>({});
const freemixQtyLock = ref<Record<string, string>>({});
const freemixMaxQty = ref<Record<string, string>>({});

const missing = computed(() => preview.value?.missing || []);

interface SuppKey {
  pn: string;
  packmatls: string;
  row_no: number | null;
  checked: boolean;
  l: string;
  w: string;
  h: string;
  tare: string;
  net: string;
  gross: string;
  max_load: string;
}
const suppKeys = ref<SuppKey[]>([]);
const suppDone = ref(false);
const suppError = ref("");

function cmToMm(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return "";
  // b_len/c_wid/d_hgt in the preview are already mm (map_raw_rows ×10)
  // the excel input the user typed was cm — convert back to cm for display
  return String(Number(v / 10).toFixed(2));
}

function initSuppKeys() {
  const um = preview.value?.unmatched || [];
  const seen = new Set<string>();
  const keys: SuppKey[] = [];
  for (const u of um) {
    const id = `${u.pn || ""}|${u.packmatls || ""}`;
    if (seen.has(id)) continue;
    seen.add(id);
    keys.push({
      pn: u.pn || "",
      packmatls: u.packmatls || "",
      row_no: u.row_no,
      checked: true,
      l: cmToMm(u.b_len),
      w: cmToMm(u.c_wid),
      h: cmToMm(u.d_hgt),
      tare: u.h_tare != null ? String(u.h_tare) : "",
      net: u.i_net != null ? String(u.i_net) : "",
      gross: u.j_gross != null ? String(u.j_gross) : "",
      max_load: "",
    });
  }
  suppKeys.value = keys;
  suppDone.value = false;
  suppError.value = "";
}

function selectedSuppKeys() {
  return suppKeys.value.filter((k) => k.checked);
}

function validateSupp(k: SuppKey): string | null {
  for (const f of ["l", "w", "h"] as const) {
    const v = Number(k[f]);
    if (!k[f] || Number.isNaN(v) || v <= 0) {
      return `${f.toUpperCase()} 需为正数`;
    }
  }
  return null;
}

async function writeSupplement() {
  const sel = selectedSuppKeys();
  if (!sel.length) {
    suppError.value = "请至少勾选一个未匹配键。";
    return;
  }
  for (const k of sel) {
    const bad = validateSupp(k);
    if (bad) {
      suppError.value = `${k.pn || k.packmatls || "未命名"}：${bad}，请填写完整再提交。`;
      return;
    }
  }
  importing.value = true;
  suppError.value = "";
  const items = sel.map((k) => ({
    pn: k.pn || undefined,
    name: k.packmatls || undefined,
    l: Number(k.l),
    w: Number(k.w),
    h: Number(k.h),
    tare: k.tare ? Number(k.tare) : undefined,
    net: k.net ? Number(k.net) : undefined,
    gross: k.gross ? Number(k.gross) : undefined,
    max_load: k.max_load ? Number(k.max_load) : undefined,
  }));
  try {
    preview.value = await Tasks.supplement(tid.value, items);
    initSuppKeys();
    suppDone.value = true;
    error.value = "";
  } catch (e) {
    suppError.value = (e as Error).message;
  } finally {
    importing.value = false;
  }
}
const stepDone = computed(() => {
  const done: number[] = [];
  if ((preview.value?.row_count || 0) > 0 && hasMode.value) done.push(1);
  if (preview.value?.site_auto_confirmed) done.push(2);
  return done;
});
const canContinue = computed(
  () => (preview.value?.row_count || 0) > 0 && hasMode.value,
);
const skipSite = computed(() => !!preview.value?.site_auto_confirmed);
const nextPath = computed(() =>
  skipSite.value ? `/tasks/${tid.value}/rules` : `/tasks/${tid.value}/site`,
);
const nextLabel = computed(() =>
  skipSite.value ? "下一步：规则配置" : "下一步：Site 确认",
);
const nextHint = computed(() => {
  if (!canContinue.value) return "完成导入与箱型设置后可继续。";
  if (skipSite.value) return "数据只有 1 个 Site（或未填 Site），已自动跳过 Site 确认。";
  return "数据与箱型已就绪。";
});
const shownRows = computed(() => {
  const rows = preview.value?.rows || [];
  if (missing.value.length && rows.length > 60) {
    return rows.filter((r) => !r.complete).slice(0, 60);
  }
  return rows;
});

async function load() {
  preview.value = await Tasks.preview(tid.value);
  initSuppKeys();
  types.value = await ContainerTypes.list();
  const task = await Tasks.get(tid.value);
  let raw: Record<string, unknown> = {};
  try {
    const v = task.container_mode_json;
    raw = typeof v === "string" ? JSON.parse(v || "{}") : (v || {});
  } catch {
    raw = {};
  }
  if (raw.mode === "freemix") {
    mode.value = "freemix";
    const typeLock = (raw.type_lock as string[]) || [];
    for (const t of types.value) freemixTypeLock.value[t.code] = typeLock.includes(t.code);
    const qtyLock = (raw.qty_lock as Record<string, number>) || {};
    for (const [k, v] of Object.entries(qtyLock)) freemixQtyLock.value[k] = String(v);
    const maxQty = (raw.max_qty as Record<string, number>) || {};
    for (const [k, v] of Object.entries(maxQty)) freemixMaxQty.value[k] = String(v);
  } else {
    mode.value = "fixed";
    // 兼容旧数据：单元素 fixed 映射到 type_code，legacy 字段优先
    const legacyType = (raw.type_code as string) || "";
    const fixed = (raw.fixed as Record<string, number>) || {};
    const entries = Object.entries(fixed);
    const legacyMaxQty = (raw.max_qty as Record<string, number>) || {};
    if (legacyType && (raw.count != null || entries.length === 0)) {
      fixedType.value = legacyType;
      fixedMaxQty.value = Number(legacyMaxQty[legacyType] ?? (raw.count as number) ?? 0);
    } else if (entries.length > 0) {
      fixedType.value = entries[0][0];
      fixedMaxQty.value = Number(legacyMaxQty[entries[0][0]] ?? entries[0][1] ?? 0);
    } else {
      fixedType.value = "";
      fixedMaxQty.value = 0;
    }
  }
  hasMode.value =
    mode.value === "fixed"
      ? fixedType.value !== ""
      : Object.values(freemixTypeLock.value).some(Boolean);
}

async function onFileSelected() {
  const file = fileInput.value?.files?.[0];
  if (!file) return;
  importing.value = true;
  error.value = "";
  try {
    const data = await Tasks.importFile(tid.value, file);
    preview.value = data;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    importing.value = false;
    fileInput.value = undefined as unknown as HTMLInputElement;
  }
}

async function saveContainerMode() {
  modeError.value = "";
  modeSaved.value = false;
  let payload: Record<string, unknown>;
  if (mode.value === "fixed") {
    const maxQty = Number(fixedMaxQty.value);
    if (!fixedType.value) {
      modeError.value = "请选择一种箱型。";
      return;
    }
    if (Number.isNaN(maxQty) || maxQty < 0 || !Number.isInteger(maxQty)) {
      modeError.value = "箱型上限需为 ≥ 0 的整数，0 表示不设上限。";
      return;
    }
    // fixed dict holds the upper limit; max_qty mirrors it for the engine
    payload = {
      mode: "fixed",
      fixed: { [fixedType.value]: maxQty },
      max_qty: { [fixedType.value]: maxQty },
    };
  } else {
    const typeLock = Object.entries(freemixTypeLock.value)
      .filter(([, v]) => v)
      .map(([k]) => k);
    if (typeLock.length === 0) {
      modeError.value = "请至少勾选一种允许参与搜索的箱型。";
      return;
    }
    const qtyLock: Record<string, number> = {};
    for (const [k, v] of Object.entries(freemixQtyLock.value)) {
      const n = Number(v);
      if (!Number.isNaN(n) && n > 0) qtyLock[k] = n;
    }
    const maxQty: Record<string, number> = {};
    for (const [k, v] of Object.entries(freemixMaxQty.value)) {
      const n = Number(v);
      if (!Number.isNaN(n) && n > 0) maxQty[k] = n;
    }
    payload = {
      mode: "freemix",
      type_lock: typeLock,
      qty_lock: qtyLock,
      max_qty: maxQty,
    };
  }
  try {
    await Tasks.update(tid.value, {
      container_mode_json: JSON.stringify(payload),
    });
    hasMode.value = true;
    modeSaved.value = true;
    error.value = "";
  } catch (e) {
    modeError.value = (e as Error).message;
  }
}

function downloadPending() {
  window.open(Tasks.pendingXlsxUrl(tid.value), "_blank");
}

function downloadMatched() {
  window.open(Tasks.matchedXlsxUrl(tid.value), "_blank");
}

async function onPendingFile() {
  const file = pendingInput.value?.files?.[0];
  if (!file) return;
  importing.value = true;
  error.value = "";
  try {
    await Tasks.batchMaintain(tid.value, file);
    preview.value = await Tasks.reMatch(tid.value);
    initSuppKeys();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    importing.value = false;
  }
}

function cellText(r: ImportRow, key: string): string {
  const v = r[key as keyof ImportRow];
  if (v == null) return "—";
  if (["b_len", "c_wid", "d_hgt"].includes(key)) {
    return (Number(v) / 10).toFixed(1);
  }
  return String(v);
}

onMounted(load);
</script>

<template>
  <div class="page">
    <StepNav :task-id="tid" :current="1" :done="stepDone" />

    <div class="top">
      <div>
        <h1>导入与箱型</h1>
        <p class="sub" v-if="preview">
          共 {{ preview.row_count }} 行 · 缺失 {{ missing.length }} 项
          <span v-if="preview.can_compute" class="badge ok">可计算</span>
          <span v-else class="badge no">缺规格，无法计算</span>
        </p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="ghost">返回任务列表</router-link>
        <button @click="downloadMatched" :disabled="!preview?.row_count">导出匹配表</button>
        <button @click="downloadPending" :disabled="!preview?.row_count">下载待填规格</button>
        <a class="link" href="/api/tasks/sample.xlsx" target="_blank">下载示例表</a>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="showGuide" class="guide-bar">
      <div class="guide-text">
        <strong>新任务配置指引</strong>
        <span>按顺序完成：导入数据 → 设置箱型 → 检查导入结果 → 补齐缺失规格 → Site 确认（单 Site 自动跳过） → 规则 → 计算。</span>
      </div>
      <button class="guide-close" @click="showGuide = false">知道了</button>
    </div>

    <section class="section">
      <div class="section-head">
        <span class="step-badge">1</span>
        <div>
          <h2>导入文件</h2>
          <p class="section-hint">支持 xlsx / xls / csv，长宽高按 cm 导入并自动换算为 mm。</p>
        </div>
      </div>
      <div class="form-row">
        <input
          type="file"
          ref="fileInput"
          accept=".xlsx,.xls,.csv"
          @change="onFileSelected"
        />
      </div>
      <p v-if="importing" class="hint">处理中…</p>
    </section>

    <section class="section">
      <div class="section-head">
        <span class="step-badge">2</span>
        <div>
          <h2>设置箱型</h2>
          <p class="section-hint">固定箱型适合单一柜型；自由组合可勾选多种箱型参与搜索。</p>
        </div>
      </div>

      <div class="mode-toggle">
        <label :class="{ active: mode === 'fixed' }">
          <input type="radio" value="fixed" v-model="mode" /> 固定箱型
        </label>
        <label :class="{ active: mode === 'freemix' }">
          <input type="radio" value="freemix" v-model="mode" /> 自由组合
        </label>
      </div>

      <div v-if="mode === 'fixed'" class="mode-body">
        <div class="hint">选择一种箱型并填写数量上限；0 表示不设上限，按货量自动估算。</div>
        <div class="form-row" style="margin-top: 8px">
          <select v-model="fixedType">
            <option value="">选择箱型</option>
            <option v-for="t in types" :key="t.id" :value="t.code">
              {{ t.code }} — {{ t.name }}
            </option>
          </select>
          <input type="number" v-model.number="fixedMaxQty" min="0" class="count" />
          <span class="hint-inline">上限（0 = 不限）</span>
        </div>
      </div>

      <div v-if="mode === 'freemix'" class="mode-body">
        <div class="hint">勾选允许参与搜索的箱型；可对某些箱型锁数量或设数量上限。</div>
        <div class="table-wrap">
          <table class="mode-tbl">
            <thead>
              <tr>
                <th>勾选</th>
                <th>箱型</th>
                <th>数量锁定</th>
                <th>数量上限</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in types" :key="t.id">
                <td><input type="checkbox" v-model="freemixTypeLock[t.code]" /></td>
                <td>{{ t.code }}</td>
                <td>
                  <input
                    v-model="freemixQtyLock[t.code]"
                    placeholder="—"
                    class="lock-input"
                  />
                </td>
                <td>
                  <input
                    v-model="freemixMaxQty[t.code]"
                    placeholder="—"
                    class="lock-input"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="form-row" style="margin-top: 10px">
        <button class="primary" @click="saveContainerMode" :disabled="importing">
          应用箱型设置
        </button>
        <span v-if="modeSaved" class="ok-text">箱型设置已保存</span>
      </div>
      <p v-if="modeError" class="error inline">{{ modeError }}</p>
      <p v-else-if="!hasMode" class="hint">计算前需先设置箱型。</p>
    </section>

    <section class="section">
      <div class="section-head">
        <span class="step-badge">3</span>
        <div>
          <h2>检查导入结果</h2>
          <p class="section-hint">N 列导入时忽略；不完整行会标黄，便于快速定位。可导出已匹配主数据规格的完整表。</p>
        </div>
      </div>
      <div class="form-row" style="margin-bottom: 10px">
        <button @click="downloadMatched" :disabled="!preview?.row_count">导出匹配表</button>
      </div>
      <div class="table-wrap">
        <table class="map-tbl">
          <thead>
            <tr>
              <th v-for="c in IMPORT_COLUMNS" :key="c.code">{{ c.code }} {{ c.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in shownRows" :key="r.id" :class="{ incomplete: !r.complete }">
              <td v-for="c in IMPORT_COLUMNS" :key="c.code">
                <template v-if="c.code === 'N'">
                  <span class="na">…</span>
                </template>
                <template v-else>{{ cellText(r, c.key) }}</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="shownRows.length < (preview?.rows.length || 0)" class="hint">
        仅显示不完整行（前 60 行），完整行已省略。
      </p>
    </section>

    <section class="section">
      <div class="section-head">
        <span class="step-badge">4</span>
        <div>
          <h2>补齐缺失规格</h2>
          <p class="section-hint">缺失长宽高的行按 PN + PackMatls 匹配主数据。可下载待填表批量补全并写回主数据。</p>
        </div>
      </div>
      <div class="form-row" style="margin-bottom: 12px">
        <button @click="downloadMatched" :disabled="!preview?.row_count">导出匹配表</button>
        <button @click="downloadPending" :disabled="!preview?.row_count">下载待填规格</button>
        <button @click="pendingInput?.click()" :disabled="importing">上传待填表</button>
        <input
          type="file"
          ref="pendingInput"
          accept=".xlsx,.xls"
          class="hidden-input"
          @change="onPendingFile"
        />
        <a class="link" href="/packages" target="_blank">打开包装主数据</a>
      </div>
      <p class="hint">下载待填表 → 补全规格 → 上传后写入主数据并自动重新匹配。匹配键为 PN + PackMatls。</p>
      <div class="table-wrap" v-if="missing.length">
        <table class="tbl">
          <thead>
            <tr>
              <th>PN</th>
              <th>PackMatls</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(m, i) in missing" :key="i">
              <td>{{ m.pn || "—" }}</td>
              <td>{{ m.packmatls || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="ok-text">所有规格已补全，可以开始计算。</p>

      <div v-if="suppKeys.length" class="supp-block">
        <h3 class="supp-title">未匹配主数据 · 一键补充</h3>
        <p class="supp-hint">勾选需要补入主数据的键，填写规格（长/宽/高必填，cm 与 kg）后一键写入主数据并自动重新匹配，供以后任务复用。</p>
        <div class="table-wrap">
          <table class="supp-tbl">
            <thead>
              <tr>
                <th>勾选</th>
                <th>PN</th>
                <th>PackMatls</th>
                <th>长cm</th>
                <th>宽cm</th>
                <th>高cm</th>
                <th>箱重kg</th>
                <th>净重kg</th>
                <th>毛重kg</th>
                <th>每箱承重kg</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="k in suppKeys" :key="`${k.pn}|${k.packmatls}`">
                <td><input type="checkbox" v-model="k.checked" /></td>
                <td>{{ k.pn || "—" }}</td>
                <td>{{ k.packmatls || "—" }}</td>
                <td><input v-model="k.l" class="supp-input" placeholder="必填" /></td>
                <td><input v-model="k.w" class="supp-input" placeholder="必填" /></td>
                <td><input v-model="k.h" class="supp-input" placeholder="必填" /></td>
                <td><input v-model="k.tare" class="supp-input" placeholder="—" /></td>
                <td><input v-model="k.net" class="supp-input" placeholder="—" /></td>
                <td><input v-model="k.gross" class="supp-input" placeholder="—" /></td>
                <td><input v-model="k.max_load" class="supp-input" placeholder="默认不限" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="form-row" style="margin-top: 10px">
          <button class="primary" @click="writeSupplement" :disabled="importing || selectedSuppKeys().length === 0">
            一键写入主数据（{{ selectedSuppKeys().length }} 条）
          </button>
          <span v-if="suppDone" class="ok-text">已写入主数据并重新匹配</span>
        </div>
        <p v-if="suppError" class="error inline">{{ suppError }}</p>
      </div>
    </section>

    <div class="next-bar">
      <span>{{ nextHint }}</span>
      <router-link
        v-if="canContinue"
        :to="nextPath"
        class="next-btn"
      >
        {{ nextLabel }}
      </router-link>
      <span v-else class="next-btn disabled">{{ nextLabel }}</span>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px 40px; max-width: 1200px; margin: 0 auto; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; display: flex; align-items: center; gap: 8px; }
.actions { display: flex; gap: 8px; align-items: center; }
.section { margin-top: 28px; }
.section-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; }
.step-badge { flex: none; width: 22px; height: 22px; border-radius: 50%; background: #eef5f0; color: #1a5c38; font-size: 12px; font-weight: 600; display: flex; align-items: center; justify-content: center; margin-top: 1px; }
.section-head h2 { margin: 0; }
.section-hint { font-size: 12px; color: #888; margin: 4px 0 0; line-height: 1.5; }
.guide-bar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid #d9e8df; background: #f4f9f6; border-radius: 8px; margin-bottom: 8px; }
.guide-text { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #436652; line-height: 1.6; }
.guide-text strong { font-size: 13px; color: #1a5c38; }
.guide-close { flex: none; padding: 4px 12px; border: 1px solid #b9d2c4; border-radius: 4px; background: #fff; color: #1a5c38; font-size: 12px; cursor: pointer; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.next-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 32px; padding: 14px 16px; border: 1px solid #e8e4e0; background: #fff; border-radius: 8px; font-size: 13px; color: #555; }
.next-btn { flex: none; padding: 7px 16px; border-radius: 4px; background: #1a5c38; color: #fff; text-decoration: none; font-size: 13px; }
.next-btn:hover { text-decoration: none; opacity: 0.9; }
.next-btn.disabled { background: #e8e4e0; color: #999; }
h2 { font-size: 16px; font-weight: 500; color: #444; margin: 0 0 12px; }
.form-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.form-row select { padding: 6px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
.count { width: 60px; padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
.hint-inline { font-size: 12px; color: #888; }
button { padding: 6px 14px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 14px; cursor: pointer; }
button.primary { background: #1a5c38; color: #fff; border-color: #1a5c38; }
button.primary:disabled { opacity: 0.4; cursor: not-allowed; }
button:disabled { opacity: 0.4; cursor: not-allowed; }
a.ghost { color: #888; text-decoration: none; font-size: 14px; }
a.link { font-size: 13px; color: #1a5c38; text-decoration: none; }
a.link:hover { text-decoration: underline; }
.hidden-input { display: none; }
.badge { font-size: 11px; padding: 1px 8px; border-radius: 3px; }
.badge.ok { background: #e8f5e9; color: #1a5c38; }
.badge.no { background: #fde8e8; color: #c62828; }
.hint { font-size: 13px; color: #888; margin: 8px 0 0; }
.error { color: #c62828; font-size: 13px; margin: 0 0 8px; }
.error.inline { margin: 8px 0 0; }
.ok-text { font-size: 14px; color: #1a5c38; margin: 0; }
.map-tbl { width: 100%; border-collapse: collapse; font-size: 12px; min-width: 1080px; }
.map-tbl th { text-align: left; color: #888; font-weight: 500; padding: 6px 8px; border-bottom: 1px solid #e8e4e0; white-space: nowrap; }
.map-tbl td { padding: 6px 8px; color: #333; border-bottom: 1px solid #f0ede8; white-space: nowrap; }
.map-tbl tr.incomplete td { background: #fff8e1; }
.map-tbl .na { color: #bbb; }

/* --- container mode picker --- */
.mode-toggle { display: flex; gap: 4px; margin-bottom: 12px; }
.mode-toggle label {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 12px; border: 1px solid #ccc; border-radius: 4px;
  font-size: 14px; cursor: pointer; color: #333;
}
.mode-toggle label.active { background: #1a5c38; color: #fff; border-color: #1a5c38; }
.mode-toggle label.active input { accent-color: #fff; }
.mode-body {
  border: 1px solid #e8e4e0; border-radius: 6px;
  padding: 12px 16px; background: #faf8f6;
}
.mode-tbl { width: 100%; border-collapse: collapse; margin-top: 8px; min-width: 520px; }
.mode-tbl th {
  text-align: left; font-size: 13px; color: #888; font-weight: 500;
  padding: 6px 10px; border-bottom: 1px solid #e8e4e0;
}
.mode-tbl td { padding: 6px 10px; font-size: 14px; color: #333; }
.mode-tbl input[type="number"], .lock-input {
  width: 60px; padding: 4px 8px;
  border: 1px solid #ccc; border-radius: 4px; font-size: 14px;
}
.tbl { width: 100%; border-collapse: collapse; min-width: 360px; }
.tbl th { text-align: left; font-size: 13px; color: #888; font-weight: 500; padding: 8px 10px; border-bottom: 1px solid #e8e4e0; }
.tbl td { padding: 8px 10px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }

.supp-block { margin-top: 16px; padding-top: 12px; border-top: 1px solid #f0ede8; }
.supp-title { font-size: 14px; font-weight: 500; color: #2c2c2c; margin: 0 0 6px; }
.supp-hint { font-size: 12px; color: #888; margin: 0 0 10px; line-height: 1.5; }
.supp-tbl { width: 100%; border-collapse: collapse; min-width: 720px; }
.supp-tbl th { text-align: left; font-size: 12px; color: #888; font-weight: 500; padding: 6px 8px; border-bottom: 1px solid #e8e4e0; }
.supp-tbl td { padding: 6px 8px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }
.supp-input { width: 72px; padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }

@media (max-width: 900px) {
  .page { padding: 24px 24px 40px; }
  .top { flex-direction: column; gap: 12px; }
}

@media (max-width: 720px) {
  .page { padding: 16px 16px 32px; }
  .actions { flex-wrap: wrap; }
  .guide-bar { flex-direction: column; gap: 10px; }
  .guide-close { align-self: flex-start; }
  .next-bar { flex-direction: column; align-items: stretch; gap: 10px; }
  .next-btn { text-align: center; }
}
</style>
