<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { Packages, type PackageMaster } from "@/api";

const items = ref<PackageMaster[]>([]);
const showForm = ref(false);
const editing = ref<PackageMaster | null>(null);
const error = ref("");
const importMsg = ref("");
const importing = ref(false);
const importInput = ref<HTMLInputElement>();
const selected = ref<Set<number>>(new Set());
const batchField = ref("max_load");
const batchValue = ref("");
const batchBusy = ref(false);

// search
const searchQuery = ref("");

// sort
type SortField =
  "pn" | "name" | "l" | "w" | "h" | "gross" | "max_load" | "max_stack" | "default_loading";
const sortField = ref<SortField>("pn");
const sortAsc = ref(true);

// pagination
const PAGE_SIZE = 40;
const currentPage = ref(1);

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return items.value;
  return items.value.filter(
    (p) =>
      (p.pn || "").toLowerCase().includes(q) ||
      (p.name || "").toLowerCase().includes(q) ||
      (p.package_type || "").toLowerCase().includes(q) ||
      (p.cargo_type || "").toLowerCase().includes(q) ||
      (p.default_loading || "").toLowerCase().includes(q),
  );
});

const sorted = computed(() => {
  const arr = [...filtered.value];
  const f = sortField.value;
  const dir = sortAsc.value ? 1 : -1;
  arr.sort((a, b) => {
    const av = a[f];
    const bv = b[f];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "string" || typeof bv === "string") {
      return String(av).localeCompare(String(bv), "zh") * dir;
    }
    return (Number(av) - Number(bv)) * dir;
  });
  return arr;
});

const totalPages = computed(() => Math.max(1, Math.ceil(sorted.value.length / PAGE_SIZE)));
const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE;
  return sorted.value.slice(start, start + PAGE_SIZE);
});
const totalCount = computed(() => sorted.value.length);

function toggleSort(field: SortField) {
  if (sortField.value === field) {
    sortAsc.value = !sortAsc.value;
  } else {
    sortField.value = field;
    sortAsc.value = true;
  }
  currentPage.value = 1;
}

function sortIndicator(field: SortField): string {
  if (sortField.value !== field) return "";
  return sortAsc.value ? " ▲" : " ▼";
}

watch(searchQuery, () => {
  currentPage.value = 1;
});

const BATCH_FIELDS = [
  { key: "max_load", label: "每箱承重 kg", kind: "load" },
  { key: "rotatable", label: "四面进铲", kind: "bool" },
  { key: "same_type_stack", label: "同种堆叠", kind: "bool" },
  { key: "default_loading", label: "默认装卸", kind: "loading" },
  { key: "max_stack", label: "最大堆码层数", kind: "number" },
  { key: "enabled", label: "启用", kind: "bool" },
  { key: "cargo_type", label: "货物类型", kind: "text" },
  { key: "package_type", label: "包装类型", kind: "text" },
] as const;

const currentBatch = computed(
  () => BATCH_FIELDS.find((f) => f.key === batchField.value) || BATCH_FIELDS[0],
);
const selectedCount = computed(() => selected.value.size);
const allSelected = computed(
  () => pagedItems.value.length > 0 && pagedItems.value.every((p) => selected.value.has(p.id)),
);

function loadingValue(v: string | null | undefined): string {
  if (v === "叉车" || v === "forklift") return "叉车";
  if (v === "人工" || v === "manual") return "人工";
  return "叉车";
}

const emptyForm = () => ({
  pn: "",
  name: "",
  package_type: "",
  cargo_type: "",
  l: 0,
  w: 0,
  h: 0,
  tare: 0,
  net: 0,
  gross: 0,
  rotatable: 1,
  same_type_stack: 0,
  default_loading: "叉车",
  max_stack: 0,
  max_load: "" as string | number,
  enabled: 1,
});

const form = ref(emptyForm());

async function load() {
  error.value = "";
  try {
    items.value = await Packages.list();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function startCreate() {
  editing.value = null;
  form.value = emptyForm();
  showForm.value = true;
}

function startEdit(p: PackageMaster) {
  editing.value = p;
  form.value = {
    pn: p.pn || "",
    name: p.name || "",
    package_type: p.package_type || "",
    cargo_type: p.cargo_type || "",
    l: p.l ?? 0,
    w: p.w ?? 0,
    h: p.h ?? 0,
    tare: p.tare ?? 0,
    net: p.net ?? 0,
    gross: p.gross ?? 0,
    rotatable: p.rotatable ?? 1,
    same_type_stack: p.same_type_stack ?? 0,
    default_loading: loadingValue(p.default_loading),
    max_stack: p.max_stack ?? 0,
    max_load: p.max_load == null ? "" : p.max_load,
    enabled: p.enabled ?? 1,
  };
  showForm.value = true;
}

function parseLoad(v: string | number): number | null {
  if (v === "" || v == null) return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

async function save() {
  error.value = "";
  try {
    const body = {
      ...form.value,
      pn: form.value.pn || null,
      name: form.value.name || null,
      default_loading: loadingValue(String(form.value.default_loading)),
      max_load: parseLoad(form.value.max_load),
    };
    if (editing.value) {
      await Packages.update(editing.value.id, body);
    } else {
      await Packages.create(body);
    }
    showForm.value = false;
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function toggleOne(id: number, on: boolean) {
  const next = new Set(selected.value);
  if (on) next.add(id);
  else next.delete(id);
  selected.value = next;
}

function toggleAll(on: boolean) {
  selected.value = on ? new Set(pagedItems.value.map((p) => p.id)) : new Set();
}

function parseBatchValue(): unknown {
  const kind = currentBatch.value.kind;
  const raw = batchValue.value;
  if (kind === "load") {
    if (raw === "" || raw === "不限") return null;
    const n = Number(raw);
    if (Number.isNaN(n) || n < 0) throw new Error("承重量需为 ≥0 的数字，留空表示不限");
    return n;
  }
  if (kind === "bool") {
    if (raw === "1" || raw === "是" || raw === "true") return 1;
    if (raw === "0" || raw === "否" || raw === "false") return 0;
    throw new Error("请选择 是 或 否");
  }
  if (kind === "loading") {
    if (raw === "forklift" || raw === "叉车") return "叉车";
    if (raw === "manual" || raw === "人工") return "人工";
    throw new Error("请选择 叉车 或 人工");
  }
  if (kind === "number") {
    const n = Number(raw);
    if (raw === "" || Number.isNaN(n) || n < 0) throw new Error("请填写 ≥0 的数字");
    return n;
  }
  return raw;
}

async function applyBatch() {
  if (!selectedCount.value) {
    error.value = "请先勾选要更新的主数据。";
    return;
  }
  error.value = "";
  importMsg.value = "";
  let value: unknown;
  try {
    value = parseBatchValue();
  } catch (e) {
    error.value = (e as Error).message;
    return;
  }
  const field = currentBatch.value.key;
  const label = currentBatch.value.label;
  if (!confirm(`将 ${selectedCount.value} 条主数据的「${label}」更新为同一值？`)) return;
  batchBusy.value = true;
  try {
    await Packages.batchUpdate([...selected.value], { [field]: value });
    importMsg.value = `已更新 ${selectedCount.value} 条「${label}」`;
    selected.value = new Set();
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    batchBusy.value = false;
  }
}

async function remove(p: PackageMaster) {
  if (!confirm(`删除包装 ${p.pn || p.name}？`)) return;
  error.value = "";
  try {
    await Packages.remove(p.id);
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function downloadTemplate() {
  window.open(Packages.templateUrl(), "_blank");
}

function downloadExport() {
  window.open(Packages.exportUrl(), "_blank");
}

async function onImportFile() {
  const file = importInput.value?.files?.[0];
  if (!file) return;
  importing.value = true;
  error.value = "";
  importMsg.value = "";
  try {
    const result = await Packages.importFile(file);
    importMsg.value =
      `已导入 ${result.saved_count} 条` +
      (result.skipped ? `，跳过 ${result.skipped} 条缺尺寸记录` : "");
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    importing.value = false;
    if (importInput.value) importInput.value.value = "";
  }
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="top">
      <div>
        <h1>包装主数据</h1>
        <p class="sub">按 PN + PackMatls 双字段匹配；尺寸 mm、重量 kg。可批量导入 Excel。</p>
      </div>
      <div class="actions">
        <button @click="downloadTemplate">下载模板</button>
        <button @click="downloadExport">导出全部</button>
        <button @click="importInput?.click()" :disabled="importing">
          {{ importing ? "导入中…" : "批量导入" }}
        </button>
        <input
          type="file"
          ref="importInput"
          accept=".xlsx,.xls"
          class="hidden-input"
          @change="onImportFile"
        />
        <button class="primary" @click="startCreate">新增</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="importMsg" class="ok-text">{{ importMsg }}</p>

    <div class="batch-bar">
      <span class="batch-count">已选 {{ selectedCount }} 条</span>
      <select v-model="batchField" @change="batchValue = ''">
        <option v-for="f in BATCH_FIELDS" :key="f.key" :value="f.key">{{ f.label }}</option>
      </select>
      <select v-if="currentBatch.kind === 'bool'" v-model="batchValue">
        <option value="">选择</option>
        <option value="1">是</option>
        <option value="0">否</option>
      </select>
      <select v-else-if="currentBatch.kind === 'loading'" v-model="batchValue">
        <option value="">选择</option>
        <option value="叉车">叉车</option>
        <option value="人工">人工</option>
      </select>
      <input
        v-else-if="currentBatch.kind === 'load'"
        v-model="batchValue"
        type="number"
        min="0"
        step="0.1"
        placeholder="留空=不限；0=不可被压"
        class="batch-input"
      />
      <input
        v-else
        v-model="batchValue"
        :type="currentBatch.kind === 'number' ? 'number' : 'text'"
        :placeholder="'新的' + currentBatch.label"
        class="batch-input"
      />
      <button class="primary" @click="applyBatch" :disabled="batchBusy || !selectedCount">
        {{ batchBusy ? "更新中…" : "应用到所选" }}
      </button>
    </div>

    <div v-if="showForm" class="form-card">
      <h2>{{ editing ? `编辑 ${editing.pn || editing.name}` : "新增包装" }}</h2>
      <div class="grid">
        <label>PN <input v-model="form.pn" :disabled="!!editing" /></label>
        <label>PackMatls <input v-model="form.name" /></label>
        <label>包装类型 <input v-model="form.package_type" /></label>
        <label>货物类型 <input v-model="form.cargo_type" /></label>
        <label>长mm <input type="number" v-model.number="form.l" /></label>
        <label>宽mm <input type="number" v-model.number="form.w" /></label>
        <label>高mm <input type="number" v-model.number="form.h" /></label>
        <label>箱重kg <input type="number" step="0.1" v-model.number="form.tare" /></label>
        <label>净重kg <input type="number" step="0.1" v-model.number="form.net" /></label>
        <label>毛重kg <input type="number" step="0.1" v-model.number="form.gross" /></label>
        <label class="ck"
          >四面进铲
          <input type="checkbox" v-model="form.rotatable" :true-value="1" :false-value="0"
        /></label>
        <label class="ck"
          >同种堆叠
          <input type="checkbox" v-model="form.same_type_stack" :true-value="1" :false-value="0"
        /></label>
        <label
          >默认装卸
          <select v-model="form.default_loading">
            <option value="叉车">叉车</option>
            <option value="人工">人工</option>
          </select>
        </label>
        <label v-if="form.same_type_stack === 1"
          >最大堆码层数 <input type="number" v-model.number="form.max_stack"
        /></label>
        <label
          >每箱承重量kg
          <input
            type="number"
            step="0.1"
            v-model="form.max_load"
            min="0"
            placeholder="留空=不限；0=不可被压"
        /></label>
        <label class="ck"
          >启用 <input type="checkbox" v-model="form.enabled" :true-value="1" :false-value="0"
        /></label>
      </div>
      <div class="form-actions">
        <button class="primary" @click="save">保存</button>
        <button @click="showForm = false">取消</button>
      </div>
    </div>

    <div class="search-bar">
      <input
        type="text"
        v-model="searchQuery"
        placeholder="搜索 PN / PackMatls / 包装类型 / 货物类型 / 装卸方式…"
        class="search-input"
      />
      <span v-if="searchQuery" class="search-result-hint">共 {{ totalCount }} 条结果</span>
    </div>

    <div class="table-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th class="chk">
              <input
                type="checkbox"
                :checked="allSelected"
                @change="toggleAll(($event.target as HTMLInputElement).checked)"
              />
            </th>
            <th class="sortable" @click="toggleSort('pn')">PN{{ sortIndicator("pn") }}</th>
            <th class="sortable" @click="toggleSort('name')">
              PackMatls{{ sortIndicator("name") }}
            </th>
            <th class="sortable" @click="toggleSort('l')">尺寸 mm{{ sortIndicator("l") }}</th>
            <th class="sortable" @click="toggleSort('gross')">毛重{{ sortIndicator("gross") }}</th>
            <th class="sortable" @click="toggleSort('max_stack')">
              堆码层数{{ sortIndicator("max_stack") }}
            </th>
            <th class="sortable" @click="toggleSort('max_load')">
              承重量{{ sortIndicator("max_load") }}
            </th>
            <th class="sortable" @click="toggleSort('default_loading')">
              默认装卸{{ sortIndicator("default_loading") }}
            </th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in pagedItems" :key="p.id">
            <td class="chk">
              <input
                type="checkbox"
                :checked="selected.has(p.id)"
                @change="toggleOne(p.id, ($event.target as HTMLInputElement).checked)"
              />
            </td>
            <td class="pn">{{ p.pn }}</td>
            <td>{{ p.name }}</td>
            <td>{{ p.l }}×{{ p.w }}×{{ p.h }}</td>
            <td>{{ p.gross }}</td>
            <td>{{ p.max_stack ?? "-" }}</td>
            <td>
              <span v-if="p.max_load === 0">不可被压</span>
              <span v-else-if="p.max_load == null">不限</span>
              <span v-else>{{ p.max_load }}kg</span>
            </td>
            <td>{{ p.default_loading || "-" }}</td>
            <td class="ops">
              <button @click="startEdit(p)">编辑</button>
              <button @click="remove(p)" class="danger">删除</button>
            </td>
          </tr>
          <tr v-if="pagedItems.length === 0">
            <td colspan="9" class="empty-hint">{{ searchQuery ? "无匹配结果" : "暂无数据" }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pagination">
      <button :disabled="currentPage <= 1" @click="currentPage--">上一页</button>
      <span class="page-info"
        >第 {{ currentPage }} / {{ totalPages }} 页 · 共 {{ totalCount }} 条</span
      >
      <button :disabled="currentPage >= totalPages" @click="currentPage++">下一页</button>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 32px 40px;
  max-width: 980px;
  margin: 0 auto;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
h1 {
  font-size: 22px;
  font-weight: 500;
  color: #2c2c2c;
  margin: 0;
}
.sub {
  font-size: 13px;
  color: #888;
  margin: 6px 0 0;
}
button.primary {
  padding: 6px 18px;
  background: #1a5c38;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
}
.error {
  color: #c62828;
  font-size: 13px;
  margin: 0 0 12px;
}
.form-card {
  border: 1px solid #e8e4e0;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 24px;
  background: #fff;
}
.form-card h2 {
  font-size: 15px;
  font-weight: 500;
  color: #444;
  margin: 0 0 12px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.grid label {
  font-size: 13px;
  color: #555;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.grid label.ck {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
.grid input {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}
.grid label.ck input {
  padding: 0;
}
.grid select {
  padding: 6px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}
.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}
.form-actions button {
  padding: 6px 16px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  font-size: 14px;
  cursor: pointer;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}
.table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.tbl th {
  text-align: left;
  font-size: 13px;
  color: #888;
  font-weight: 500;
  padding: 8px 12px;
  border-bottom: 1px solid #e8e4e0;
}
.tbl td {
  padding: 10px 12px;
  font-size: 14px;
  color: #333;
  border-bottom: 1px solid #f0ede8;
}
.tbl .pn {
  font-weight: 600;
  color: #1a5c38;
}
.ops {
  display: flex;
  gap: 6px;
}
.ops button {
  padding: 3px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
}
.ops button.danger {
  color: #c62828;
  border-color: #c62828;
}
.actions button {
  padding: 6px 14px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  font-size: 14px;
  cursor: pointer;
}
.actions button.primary {
  background: #1a5c38;
  color: #fff;
  border-color: #1a5c38;
}
.actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.hidden-input {
  display: none;
}
.ok-text {
  color: #1a5c38;
  font-size: 13px;
  margin: 0 0 12px;
}
.batch-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin: 0 0 14px;
  padding: 10px 12px;
  background: #f7f5f2;
  border-radius: 6px;
}
.batch-count {
  font-size: 13px;
  color: #555;
  min-width: 72px;
}
.batch-bar select,
.batch-input {
  padding: 5px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
}
.batch-input {
  width: 180px;
}
.batch-bar button {
  padding: 5px 14px;
}
.tbl .chk {
  width: 28px;
}

.search-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}
.search-input {
  flex: 1;
  max-width: 420px;
  padding: 7px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
}
.search-input:focus {
  outline: none;
  border-color: #1a5c38;
}
.search-result-hint {
  font-size: 12px;
  color: #888;
  white-space: nowrap;
}

.tbl th.sortable {
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}
.tbl th.sortable:hover {
  color: #1a5c38;
}

.pagination {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  margin-top: 14px;
}
.pagination button {
  padding: 4px 14px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}
.pagination button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.pagination .page-info {
  font-size: 13px;
  color: #666;
}
.empty-hint {
  text-align: center;
  color: #999;
  padding: 24px;
  font-size: 14px;
}

:root[data-theme="dark"] .search-input {
  border-color: #444;
  background: #2a2a2a;
  color: #e8e8e8;
}
:root[data-theme="dark"] .search-input:focus {
  border-color: #3d8c64;
}
:root[data-theme="dark"] .tbl th.sortable:hover {
  color: #4dd0a0;
}
:root[data-theme="dark"] .pagination button {
  background: #2a2a2a;
  border-color: #444;
  color: #ccc;
}
:root[data-theme="dark"] .pagination .page-info {
  color: #888;
}
:root[data-theme="dark"] .empty-hint {
  color: #666;
}
:root[data-theme="dark"] .search-result-hint {
  color: #888;
}

@media (max-width: 900px) {
  .page {
    padding: 24px 24px 40px;
  }
  .top {
    flex-direction: column;
    gap: 12px;
  }
  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page {
    padding: 16px 16px 32px;
  }
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
