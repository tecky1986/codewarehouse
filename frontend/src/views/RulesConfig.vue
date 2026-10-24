<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Tasks, type Task, type ImportPreview } from "@/api";

const route = useRoute();
const router = useRouter();
const tid = ref(Number(route.params.id));
const task = ref<Task | null>(null);
const preview = ref<ImportPreview | null>(null);
const rulesSavedOnce = ref(false);
const saving = ref(false);
const saved = ref(false);
const error = ref("");

const stepDone = computed(() => {
  const done: number[] = [];
  if (task.value?.container_mode_json) done.push(1);
  if (preview.value?.site_auto_confirmed || task.value?.site_groups_json) done.push(2);
  if (rulesSavedOnce.value) done.push(3);
  return done;
});

const ALL_RULES = [
  { key: "site_together", label: "Site 同柜" },
  { key: "pn_continuous", label: "PN 连续" },
  { key: "site_separate", label: "Site 分离" },
  { key: "same_type_stack", label: "同种堆叠" },
  { key: "crush", label: "易压" },
  { key: "weight_order", label: "轻重" },
  { key: "fork_tine", label: "装卸" },
];

const rules = ref<Record<string, boolean>>({});
const ruleOrder = ref<string[]>([]);

async function load() {
  task.value = await Tasks.get(tid.value);
  preview.value = await Tasks.preview(tid.value);
  let enabled: string[] = [];
  const raw = task.value!.rules_json;
  if (raw) {
    const parsed = typeof raw === "string" ? JSON.parse(raw || "[]") : raw;
    if (Array.isArray(parsed)) enabled = parsed;
    rulesSavedOnce.value = true;
  }
  ruleOrder.value = enabled.filter((k) => ALL_RULES.some((r) => r.key === k));
  for (const r of ALL_RULES) {
    if (!ruleOrder.value.includes(r.key)) ruleOrder.value.push(r.key);
  }
  for (const r of ALL_RULES) rules.value[r.key] = enabled.includes(r.key);
}

function move(key: string, dir: -1 | 1) {
  const idx = ruleOrder.value.indexOf(key);
  const target = idx + dir;
  if (target < 0 || target >= ruleOrder.value.length) return;
  const arr = [...ruleOrder.value];
  [arr[idx], arr[target]] = [arr[target], arr[idx]];
  ruleOrder.value = arr;
  saved.value = false;
}

async function save() {
  const enabled = ruleOrder.value.filter((k) => rules.value[k]);
  saving.value = true;
  saved.value = false;
  error.value = "";
  try {
    await Tasks.update(tid.value, {
      rules_json: JSON.stringify(enabled),
    });
    task.value!.rules_json = JSON.stringify(enabled);
    rulesSavedOnce.value = true;
    saved.value = true;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    saving.value = false;
  }
}

async function saveAndNext() {
  await save();
  if (saved.value) {
    await router.push(`/tasks/${tid.value}#compute`);
  }
}

onMounted(load);
</script>

<template>
  <div class="page">
    <StepNav :task-id="tid" :current="3" :done="stepDone" />

    <div class="top">
      <div>
        <h1>规则配置</h1>
        <p class="sub">启用规则按优先级从高到低排列；↑↓ 调整顺序，勾选启用。</p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="ghost">返回任务列表</router-link>
        <button class="primary" @click="save" :disabled="saving">保存</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="ok">已保存</p>

    <div class="rule-list">
      <div v-for="(key, i) in ruleOrder" :key="key" class="rule-row" :class="{ off: !rules[key] }">
        <input
          type="checkbox"
          :checked="rules[key]"
          @change="rules[key] = !rules[key]; saved = false"
        />
        <span class="prio">P{{ i + 1 }}</span>
        <span class="label">{{ ALL_RULES.find((r) => r.key === key)?.label }}</span>
        <div class="btns">
          <button @click="move(key, -1)" :disabled="i === 0" title="上移">↑</button>
          <button @click="move(key, 1)" :disabled="i === ruleOrder.length - 1" title="下移">↓</button>
        </div>
      </div>
    </div>
    <div class="next-bar">
      <span>规则按当前顺序生效，保存后进入计算。</span>
      <button class="next-btn" @click="saveAndNext" :disabled="saving">
        保存并去计算
      </button>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px 40px; max-width: 700px; margin: 0 auto; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; }
.actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
button.primary { padding: 6px 18px; background: #1a5c38; color: #fff; border: none; border-radius: 4px; font-size: 14px; cursor: pointer; }
button.primary:disabled { opacity: 0.5; }
a.ghost { color: #888; text-decoration: none; font-size: 14px; }
.error { color: #c62828; font-size: 13px; margin: 0 0 8px; }
.ok { color: #1a5c38; font-size: 13px; margin: 0 0 8px; }
.rule-list { display: flex; flex-direction: column; gap: 8px; }
.rule-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border: 1px solid #e8e4e0; border-radius: 6px; background: #fff; }
.rule-row.off { opacity: 0.55; }
.rule-row input { cursor: pointer; }
.prio { font-size: 12px; color: #888; min-width: 26px; }
.label { flex: 1; font-size: 14px; color: #333; }
.btns { display: flex; gap: 4px; }
.btns button { padding: 2px 8px; border: 1px solid #ccc; border-radius: 3px; background: #fff; cursor: pointer; font-size: 12px; }
.btns button:disabled { opacity: 0.3; cursor: not-allowed; }
.next-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 24px; padding: 14px 16px; border: 1px solid #e8e4e0; background: #fff; border-radius: 8px; font-size: 13px; color: #555; }
.next-btn { flex: none; padding: 7px 16px; border-radius: 4px; background: #1a5c38; color: #fff; border: none; font-size: 13px; cursor: pointer; }
.next-btn:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 900px) {
  .page { padding: 24px 24px 40px; }
  .top { flex-direction: column; gap: 12px; }
}

@media (max-width: 720px) {
  .page { padding: 16px 16px 32px; }
  .next-bar { flex-direction: column; align-items: stretch; gap: 10px; }
  .next-btn { width: 100%; }
}
</style>
