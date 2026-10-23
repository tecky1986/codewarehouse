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

const route = useRoute();
const tid = ref(Number(route.params.id));

const preview = ref<ImportPreview | null>(null);
const types = ref<ContainerType[]>([]);
const importing = ref(false);
const error = ref("");
const fileInput = ref<HTMLInputElement>();
const pendingInput = ref<HTMLInputElement>();
const hasMode = ref(false);

// mode: "fixed" | "freemix"
const mode = ref<"fixed" | "freemix">("fixed");
// fixed: map code -> count
const fixedCounts = ref<Record<string, number>>({});
// freemix: type lock + qty lock + max
const freemixTypeLock = ref<Record<string, boolean>>({});
const freemixQtyLock = ref<Record<string, string>>({});
const freemixMaxQty = ref<Record<string, string>>({});

const missing = computed(() => preview.value?.missing || []);
const shownRows = computed(() => {
  const rows = preview.value?.rows || [];
  if (missing.value.length && rows.length > 60) {
    return rows.filter((r) => !r.complete).slice(0, 60);
  }
  return rows;
});

async function load() {
  preview.value = await Tasks.preview(tid.value);
  types.value = await ContainerTypes.list();
  const task = await Tasks.get(tid.value);
  let raw: Record<string, unknown> = {};
  try {
    raw = JSON.parse(task.container_mode_json || "{}");
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
    const fixed = (raw.fixed as Record<string, number>) || {};
    for (const [code, n] of Object.entries(fixed)) fixedCounts.value[code] = n;
    if (raw.type_code && !fixed[raw.type_code as string]) {
      fixedCounts.value[raw.type_code as string] = (raw.count as number) || 1;
    }
  }
  hasMode.value =
    mode.value === "fixed"
      ? Object.keys(fixedCounts.value).length > 0
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
  let payload: Record<string, unknown>;
  if (mode.value === "fixed") {
    const fixed: Record<string, number> = {};
    for (const [code, n] of Object.entries(fixedCounts.value)) {
      const v = Number(n);
      if (v > 0) fixed[code] = v;
    }
    if (Object.keys(fixed).length === 0) return;
    payload = { mode: "fixed", fixed };
  } else {
    const typeLock = Object.entries(freemixTypeLock.value)
      .filter(([, v]) => v)
      .map(([k]) => k);
    if (typeLock.length === 0) return;
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
  await Tasks.update(tid.value, {
    container_mode_json: JSON.stringify(payload),
  });
  hasMode.value = true;
  error.value = "";
}

function downloadPending() {
  window.open(Tasks.pendingXlsxUrl(tid.value), "_blank");
}

async function onPendingFile() {
  const file = pendingInput.value?.files?.[0];
  if (!file) return;
  importing.value = true;
  error.value = "";
  try {
    await Tasks.batchMaintain(tid.value, file);
    preview.value = await Tasks.reMatch(tid.value);
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
    <div class="top">
      <div>
        <h1>导入预览</h1>
        <p class="sub" v-if="preview">
          共 {{ preview.row_count }} 行 · 缺失 {{ missing.length }} 项
          <span v-if="preview.can_compute" class="badge ok">可计算</span>
          <span v-else class="badge no">缺规格，无法计算</span>
        </p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="ghost">返回</router-link>
        <button @click="downloadPending" :disabled="!preview?.row_count">下载待填规格</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="section">
      <h2>箱型设置</h2>

      <!-- mode toggle -->
      <div class="mode-toggle">
        <label :class="{ active: mode === 'fixed' }">
          <input type="radio" value="fixed" v-model="mode" /> 固定箱型
        </label>
        <label :class="{ active: mode === 'freemix' }">
          <input type="radio" value="freemix" v-model="mode" /> 自由组合
        </label>
      </div>

      <!-- fixed: per-type counts -->
      <div v-if="mode === 'fixed'" class="mode-body">
        <div class="hint">勾选箱型并填写数量；同箱型或多箱型均可。</div>
        <table class="mode-tbl">
          <thead>
            <tr>
              <th v-for="t in types" :key="t.id">{{ t.code }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td v-for="t in types" :key="t.id">
                <input
                  type="number"
                  min="0"
                  v-model.number="fixedCounts[t.code]"
                  placeholder="0"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- freemix: type lock + qty lock + max -->
      <div v-if="mode === 'freemix'" class="mode-body">
        <div class="hint">勾选允许参与搜索的箱型；可对某些箱型锁数量或设数量上限。</div>
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

      <div class="form-row" style="margin-top: 10px">
        <button class="primary" @click="saveContainerMode" :disabled="importing">
          应用箱型设置
        </button>
      </div>
      <p v-if="!hasMode" class="hint">计算前需先设置箱型。</p>
    </section>

    <section class="section">
      <h2>导入文件</h2>
      <div class="form-row">
        <input
          type="file"
          ref="fileInput"
          accept=".xlsx,.xls,.csv"
          @change="onFileSelected"
        />
      </div>
      <div class="form-row" style="margin-top: 10px">
        <a class="link" href="#batch" @click.prevent="pendingInput?.click()">
          批量维护缺失规格
        </a>
        <input
          type="file"
          ref="pendingInput"
          accept=".xlsx,.xls,.csv"
          class="hidden-input"
          @change="onPendingFile"
        />
        <p class="hint">下载待填表 → 补全规格 → 上传待填表 → 自动重新匹配主数据。</p>
      </div>
      <p v-if="importing" class="hint">处理中…</p>
    </section>

    <section class="section">
      <h2>列映射（A–Q）</h2>
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
      <p v-if="shownRows.length < (preview?.rows.length || 0)" class="hint">
        仅显示不完整行（前 60 行），完整行已省略。
      </p>
    </section>

    <section class="section">
      <h2>缺失 PN / PackMatls</h2>
      <table v-if="missing.length" class="tbl">
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
      <p v-else class="ok-text">所有规格已补全，可以开始计算。</p>
    </section>
  </div>
</template>

<style scoped>
.page { padding: 32px 40px; max-width: 1200px; margin: 0 auto; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; display: flex; align-items: center; gap: 8px; }
.actions { display: flex; gap: 8px; align-items: center; }
.section { margin-top: 28px; }
h2 { font-size: 16px; font-weight: 500; color: #444; margin: 0 0 12px; }
.form-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.form-row select { padding: 6px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
.count { width: 60px; padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
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
.ok-text { font-size: 14px; color: #1a5c38; margin: 0; }
.map-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
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
.mode-tbl { width: 100%; border-collapse: collapse; margin-top: 8px; }
.mode-tbl th {
  text-align: left; font-size: 13px; color: #888; font-weight: 500;
  padding: 6px 10px; border-bottom: 1px solid #e8e4e0;
}
.mode-tbl td { padding: 6px 10px; font-size: 14px; color: #333; }
.mode-tbl input[type="number"], .lock-input {
  width: 60px; padding: 4px 8px;
  border: 1px solid #ccc; border-radius: 4px; font-size: 14px;
}
.tbl { width: 100%; border-collapse: collapse; }
.tbl th { text-align: left; font-size: 13px; color: #888; font-weight: 500; padding: 8px 10px; border-bottom: 1px solid #e8e4e0; }
.tbl td { padding: 8px 10px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }
</style>
