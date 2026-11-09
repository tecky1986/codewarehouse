<script setup lang="ts">
import { ref, onMounted, computed, watch } from "vue";
import { useRouter } from "vue-router";
import { Tasks, type Task } from "@/api";
import FirstUseGuide from "@/components/FirstUseGuide.vue";

const router = useRouter();
const tasks = ref<Task[]>([]);
const newTaskName = ref("");
const loading = ref(false);
const creating = ref(false);
const error = ref("");

const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  configuring: "配置中",
  ready: "待计算",
  computing: "计算中",
  completed: "已完成",
  failed: "失败",
};

const STATUS_OPTIONS = Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }));

const searchQuery = ref("");
const statusFilter = ref("all");

type SortField = "id" | "name" | "status" | "created_at";
const sortField = ref<SortField>("id");
const sortAsc = ref(false);

const PAGE_SIZE = 20;
const currentPage = ref(1);

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return tasks.value.filter((t) => {
    if (statusFilter.value !== "all" && (t.status || "draft") !== statusFilter.value) return false;
    if (!q) return true;
    return (t.name || "").toLowerCase().includes(q) || String(t.id).includes(q);
  });
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
const pagedTasks = computed(() => {
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

watch([searchQuery, statusFilter], () => {
  currentPage.value = 1;
});

function statusLabel(t: Task): string {
  return STATUS_LABEL[t.status || "draft"] || t.status || "草稿";
}

function taskHref(t: Task): string {
  const status = t.status || "draft";
  if (status === "draft") return `/tasks/${t.id}/import?guide=1`;
  if (status === "configuring") return `/tasks/${t.id}/import?guide=1`;
  if (status === "ready") return `/tasks/${t.id}#compute`;
  if (status === "computing" || status === "completed" || status === "failed")
    return `/tasks/${t.id}`;
  return `/tasks/${t.id}/import?guide=1`;
}

const modeLabel = computed(() => (t: Task) => {
  let m: Record<string, unknown> = {};
  try {
    const v = t.container_mode_json;
    m = typeof v === "string" ? JSON.parse(v || "{}") : v || {};
  } catch {
    m = {};
  }
  if (m.mode === "freemix") {
    const lock = (m.type_lock as string[]) || [];
    const locked = (m.qty_lock as Record<string, number>) || {};
    const parts = lock.map((c) => (locked[c] ? `${c}=${locked[c]}` : c));
    return `自由组合：${parts.join(", ") || "未设"}`;
  }
  const fixed = (m.fixed as Record<string, number>) || {};
  const entries = Object.entries(fixed);
  if (entries.length) {
    const [code, n] = entries[0];
    return Number(n) > 0 ? `${code} ≤ ${n}` : `${code} 不限`;
  }
  if (m.type_code) {
    const n = m.count ?? 0;
    return Number(n) > 0 ? `${m.type_code} ≤ ${n}` : `${m.type_code} 不限`;
  }
  return "未设置";
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    tasks.value = await Tasks.list();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}

async function createTask() {
  const name = newTaskName.value.trim();
  if (!name || creating.value) return;
  creating.value = true;
  error.value = "";
  try {
    const task = await Tasks.create(name);
    newTaskName.value = "";
    await router.push(`/tasks/${task.id}/import?guide=1`);
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    creating.value = false;
  }
}

async function removeTask(t: Task) {
  if (!confirm(`删除任务「${t.name}」？`)) return;
  error.value = "";
  try {
    await Tasks.remove(t.id);
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

onMounted(load);
</script>

<template>
  <div class="page">
    <FirstUseGuide :task-id="tasks[0]?.id ?? null" />

    <div class="top">
      <div>
        <h1>任务</h1>
        <p class="sub">新建后按「导入数据 → 设置箱型 → Site 确认 → 规则 → 计算」逐步完成。</p>
      </div>
      <div class="create-row">
        <input v-model="newTaskName" placeholder="新任务名称" @keyup.enter="createTask" />
        <button class="primary" @click="createTask" :disabled="!newTaskName.trim() || creating">
          {{ creating ? "创建中…" : "新建并配置" }}
        </button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="tasks.length" class="filter-bar">
      <input
        type="text"
        v-model="searchQuery"
        placeholder="搜索任务名称或 ID…"
        class="search-input"
      />
      <select v-model="statusFilter" class="status-select">
        <option value="all">全部状态</option>
        <option v-for="s in STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</option>
      </select>
      <span v-if="searchQuery || statusFilter !== 'all'" class="filter-hint"
        >共 {{ totalCount }} 条结果</span
      >
    </div>

    <div v-if="tasks.length" class="table-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th class="sortable" @click="toggleSort('id')">ID{{ sortIndicator("id") }}</th>
            <th class="sortable" @click="toggleSort('name')">名称{{ sortIndicator("name") }}</th>
            <th class="sortable" @click="toggleSort('status')">
              状态{{ sortIndicator("status") }}
            </th>
            <th>箱型</th>
            <th class="sortable" @click="toggleSort('created_at')">
              创建{{ sortIndicator("created_at") }}
            </th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in pagedTasks" :key="t.id">
            <td>{{ t.id }}</td>
            <td>
              <router-link :to="taskHref(t)">{{ t.name }}</router-link>
            </td>
            <td>
              <span class="status" :class="t.status || 'draft'">{{ statusLabel(t) }}</span>
            </td>
            <td>{{ modeLabel(t) }}</td>
            <td>{{ t.created_at ? t.created_at.replace("T", " ").slice(0, 16) : "" }}</td>
            <td class="ops">
              <router-link :to="taskHref(t)" class="cfg">{{
                t.status === "completed" ? "查看" : "继续配置"
              }}</router-link>
              <button @click="removeTask(t)" class="danger">删除</button>
            </td>
          </tr>
          <tr v-if="pagedTasks.length === 0">
            <td colspan="6" class="empty-hint">无匹配任务</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="tasks.length && totalPages > 1" class="pagination">
      <button :disabled="currentPage <= 1" @click="currentPage--">上一页</button>
      <span class="page-info"
        >第 {{ currentPage }} / {{ totalPages }} 页 · 共 {{ totalCount }} 条</span
      >
      <button :disabled="currentPage >= totalPages" @click="currentPage++">下一页</button>
    </div>

    <p v-else-if="!loading && !tasks.length" class="empty">
      暂无任务。输入名称后点击「新建并配置」，会直接进入导入向导。
    </p>
    <p v-if="loading" class="loading">加载中…</p>
  </div>
</template>

<style scoped>
.page {
  padding: 32px 40px;
  max-width: 960px;
  margin: 0 auto;
}

.top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
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
  line-height: 1.5;
}

.create-row {
  display: flex;
  gap: 8px;
  flex: none;
}

.create-row input {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  width: 180px;
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

button.primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  min-width: 640px;
}

.table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-radius: 8px;
}

.tbl th {
  text-align: left;
  font-weight: 500;
  font-size: 13px;
  color: #888;
  padding: 8px 12px;
  border-bottom: 1px solid #e8e4e0;
}

.tbl td {
  padding: 10px 12px;
  font-size: 14px;
  border-bottom: 1px solid #f0ede8;
  color: #333;
}

.ops {
  text-align: right;
}

.ops {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  align-items: center;
}
.ops .cfg {
  padding: 3px 10px;
  border: 1px solid #1a5c38;
  border-radius: 4px;
  background: #fff;
  font-size: 12px;
  color: #1a5c38;
  text-decoration: none;
}
.ops .cfg:hover {
  background: #eef5f0;
  text-decoration: none;
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

.status {
  display: inline-block;
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 10px;
  background: #f0ede8;
  color: #666;
}
.status.configuring {
  background: #eef5f0;
  color: #1a5c38;
}
.status.ready {
  background: #fff8e1;
  color: #8a6d1b;
}
.status.computing {
  background: #e8f0fe;
  color: #1a4a8c;
}
.status.completed {
  background: #e8f5e9;
  color: #1a5c38;
}
.status.failed {
  background: #fde8e8;
  color: #c62828;
}

a {
  color: #1a5c38;
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

.empty,
.loading {
  color: #999;
  font-size: 14px;
  padding: 24px 0;
  text-align: center;
}

.filter-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.search-input {
  flex: 1;
  min-width: 160px;
  max-width: 320px;
  padding: 7px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
}

.search-input:focus {
  outline: none;
  border-color: #1a5c38;
}

.status-select {
  padding: 7px 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
}

.filter-hint {
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

:root[data-theme="dark"] .search-input,
:root[data-theme="dark"] .status-select {
  background: #2a2a2a;
  border-color: #444;
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

:root[data-theme="dark"] .pagination .page-info,
:root[data-theme="dark"] .filter-hint,
:root[data-theme="dark"] .empty-hint {
  color: #888;
}

.error {
  color: #c62828;
  font-size: 13px;
  margin: 0;
}

@media (max-width: 720px) {
  .page {
    padding: 20px 16px 32px;
  }

  .top {
    flex-direction: column;
    gap: 12px;
  }

  .create-row {
    width: 100%;
  }

  .create-row input {
    flex: 1;
    width: auto;
    min-width: 0;
  }

  .create-row button.primary {
    flex: none;
  }
}
</style>
