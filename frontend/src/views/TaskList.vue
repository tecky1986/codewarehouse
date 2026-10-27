<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
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

function statusLabel(t: Task): string {
  return STATUS_LABEL[t.status || "draft"] || t.status || "草稿";
}

function taskHref(t: Task): string {
  const status = t.status || "draft";
  if (status === "draft") return `/tasks/${t.id}/import?guide=1`;
  if (status === "configuring") return `/tasks/${t.id}/import?guide=1`;
  if (status === "ready") return `/tasks/${t.id}#compute`;
  if (status === "computing" || status === "completed" || status === "failed") return `/tasks/${t.id}`;
  return `/tasks/${t.id}/import?guide=1`;
}

const modeLabel = computed(() => (t: Task) => {
  let m: Record<string, unknown> = {};
  try {
    const v = t.container_mode_json;
    m = typeof v === "string" ? JSON.parse(v || "{}") : (v || {});
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
  await Tasks.remove(t.id);
  await load();
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
        <input
          v-model="newTaskName"
          placeholder="新任务名称"
          @keyup.enter="createTask"
        />
        <button class="primary" @click="createTask" :disabled="!newTaskName.trim() || creating">
          {{ creating ? "创建中…" : "新建并配置" }}
        </button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="tasks.length" class="table-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>ID</th>
            <th>名称</th>
            <th>状态</th>
            <th>箱型</th>
            <th>创建</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in tasks" :key="t.id">
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
              <router-link :to="taskHref(t)" class="cfg">{{ t.status === "completed" ? "查看" : "继续配置" }}</router-link>
              <button @click="removeTask(t)" class="danger">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading" class="empty">
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
.ops .cfg:hover { background: #eef5f0; text-decoration: none; }
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
.status.configuring { background: #eef5f0; color: #1a5c38; }
.status.ready { background: #fff8e1; color: #8a6d1b; }
.status.computing { background: #e8f0fe; color: #1a4a8c; }
.status.completed { background: #e8f5e9; color: #1a5c38; }
.status.failed { background: #fde8e8; color: #c62828; }

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
