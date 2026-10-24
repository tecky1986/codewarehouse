<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute } from "vue-router";
import {
  Tasks,
  Plans,
  ContainerTypes,
  ALGORITHMS,
  type Task,
  type Plan,
  type Placement,
  type ContainerType,
  type Job,
  type ImportPreview,
} from "@/api";
import View3D from "@/components/View3D.vue";
import JobProgress from "@/components/JobProgress.vue";
import StepNav from "@/components/StepNav.vue";

const route = useRoute();
const tid = computed(() => Number(route.params.id));

const task = ref<Task | null>(null);
const plans = ref<Plan[]>([]);
const selectedPlan = ref<Plan | null>(null);
const placements = ref<Placement[]>([]);
const jobId = ref<number | null>(null);
const showJob = ref(false);
const containers = ref<ContainerType[]>([]);
const preview = ref<ImportPreview | null>(null);
const error = ref("");

const selected = ref<Placement | null>(null);
const algos = ref<string[]>(ALGORITHMS.map((a) => a.key));

const _parseJsonField = (v: unknown): Record<string, unknown> => {
  if (v == null) return {};
  if (typeof v === "string") {
    try {
      return JSON.parse(v) || {};
    } catch {
      return {};
    }
  }
  if (typeof v === "object") return v as Record<string, unknown>;
  return {};
};

const mode = computed(() => {
  if (!task.value) return null;
  const m = _parseJsonField(task.value.container_mode_json);
  if (m.mode === "freemix") {
    const lock = (m.type_lock as string[]) || [];
    if (!lock.length) return null;
    return m;
  }
  const fixed = (m.fixed as Record<string, number>) || {};
  if (Object.keys(fixed).length) return m;
  if (m.type_code) return m;
  return null;
});

const modeSummary = computed(() => {
  if (!mode.value) return null;
  const m = mode.value as Record<string, unknown>;
  if (m.mode === "freemix") {
    const lock = (m.type_lock as string[]) || [];
    return `自由组合：${lock.join(", ")}`;
  }
  const fixed = (m.fixed as Record<string, number>) || {};
  const entries = Object.entries(fixed);
  if (entries.length) {
    const [code, n] = entries[0];
    return `${code} × ${n}`;
  }
  if (m.type_code) return `${m.type_code} × ${m.count ?? 1}`;
  return null;
});

const enabledRules = computed(() => {
  const r = _parseJsonField(task.value?.rules_json);
  if (Array.isArray(r)) return r;
  return [];
});

const importedCount = computed(() => preview.value?.row_count || 0);

const siteConfigured = computed(() => {
  if (preview.value?.site_auto_confirmed) return true;
  const raw = task.value?.site_groups_json;
  if (raw == null) return false;
  let parsed: unknown = raw;
  if (typeof raw === "string") {
    try {
      parsed = JSON.parse(raw || "null");
    } catch {
      return false;
    }
  }
  if (Array.isArray(parsed)) return parsed.length > 0;
  if (parsed && typeof parsed === "object") {
    return Object.keys(parsed as Record<string, unknown>).length > 0;
  }
  return false;
});

const configSteps = computed(() => [
  {
    n: 1,
    label: "导入数据并设置箱型",
    done: importedCount.value > 0 && !!mode.value,
    to: `/tasks/${tid.value}/import`,
  },
  {
    n: 2,
    label: "确认 Site 分组",
    done: siteConfigured.value,
    to: `/tasks/${tid.value}/site`,
  },
  {
    n: 3,
    label: "配置装箱规则",
    done: task.value?.rules_json != null,
    to: `/tasks/${tid.value}/rules`,
  },
  {
    n: 4,
    label: "生成装箱方案",
    done: plans.value.length > 0,
    to: `/tasks/${tid.value}#compute`,
  },
]);

const doneSteps = computed(() =>
  configSteps.value.filter((s) => s.done).map((s) => s.n),
);

const nextConfig = computed(
  () => configSteps.value.find((s) => !s.done) || null,
);

const progressPct = computed(() =>
  Math.round((doneSteps.value.length / configSteps.value.length) * 100),
);

const canCompute = computed(() => {
  const missing: string[] = [];
  if (!mode.value) missing.push("未设置箱型");
  if (algos.value.length === 0) missing.push("未选算法");
  return missing;
});

async function loadTask() {
  error.value = "";
  try {
    task.value = await Tasks.get(tid.value);
    containers.value = await ContainerTypes.list();
    try {
      preview.value = await Tasks.preview(tid.value);
    } catch {
      preview.value = null;
    }
    await loadPlans();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function loadPlans() {
  plans.value = await Tasks.plans(tid.value);
  const adopted =
    plans.value.find((p) => p.is_adopted === 1) || plans.value[0];
  selectedPlan.value = adopted || null;
  if (selectedPlan.value) await loadPlacements(selectedPlan.value.id);
}

async function loadPlacements(planId: number) {
  placements.value = await Plans.placements(planId);
  selected.value = null;
}

async function selectPlan(p: Plan) {
  selectedPlan.value = p;
  await loadPlacements(p.id);
}

async function startCompute() {
  if (!task.value) return;
  error.value = "";
  try {
    const job = await Tasks.compute(task.value.id, { algorithms: algos.value });
    jobId.value = job.id;
    showJob.value = true;
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function onJobDone(_job: Job) {
  await loadPlans();
  showJob.value = false;
}

async function onJobFailed(_job: Job) {
  showJob.value = false;
}

async function adopt(p: Plan) {
  if (!task.value) return;
  error.value = "";
  try {
    await Tasks.adopt(task.value.id, p.id);
    await loadPlans();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function exportXlsx() {
  if (!selectedPlan.value) return;
  window.open(Plans.exportUrl(selectedPlan.value.id, "xlsx"), "_blank");
}

function exportCsv() {
  if (!selectedPlan.value) return;
  window.open(Plans.exportUrl(selectedPlan.value.id, "csv"), "_blank");
}

function onSelect(p: Placement | null) {
  selected.value = p;
}

function toggleAlgo(key: string) {
  const i = algos.value.indexOf(key);
  if (i >= 0) algos.value.splice(i, 1);
  else algos.value.push(key);
}

function ruleLabel(key: string): string {
  const map: Record<string, string> = {
    site_together: "Site 同柜",
    pn_continuous: "PN 连续",
    site_separate: "Site 分离",
    same_type_stack: "同种堆叠",
    crush: "易压",
    weight_order: "轻重",
    fork_tine: "装卸",
  };
  return map[key] || key;
}

onMounted(loadTask);
</script>

<template>
  <div class="page" v-if="task">
    <StepNav :task-id="task.id" :current="4" :done="doneSteps" />

    <div class="top">
      <div>
        <h1>{{ task.name }}</h1>
        <p class="sub">
          数据 {{ importedCount }} 行 · 方案 {{ plans.length }} 个
          <span v-if="task.created_at">
            · 创建于 {{ task.created_at.replace("T", " ").slice(0, 16) }}
          </span>
        </p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="ghost">返回任务列表</router-link>
      </div>
    </div>

    <section class="guide-card">
      <div class="guide-head">
        <div>
          <h2>配置进度</h2>
          <p class="guide-sub">已完成 {{ doneSteps.length }} / {{ configSteps.length }} 步</p>
        </div>
        <span class="guide-pct">{{ progressPct }}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div class="checklist">
        <router-link
          v-for="s in configSteps"
          :key="s.n"
          :to="s.to"
          class="check-item"
          :class="{ done: s.done }"
        >
          <span class="check-num">{{ s.n }}</span>
          <span class="check-label">{{ s.label }}</span>
          <span class="check-state">{{ s.done ? "已完成" : "待完成" }}</span>
        </router-link>
      </div>
      <div class="guide-next">
        <template v-if="nextConfig">
          <span>下一步：{{ nextConfig.label }}</span>
          <router-link :to="nextConfig.to" class="next-btn">继续配置</router-link>
        </template>
        <template v-else>
          <span>配置已完成，可以开始计算。</span>
          <a href="#compute" class="next-btn">开始计算</a>
        </template>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="info-grid">
      <div class="info-item">
        <span class="k">箱型模式</span>
        <span class="v">
          <template v-if="modeSummary">{{ modeSummary }}</template>
          <template v-else class="dim">未设置（<router-link :to="`/tasks/${task.id}/import`">去设置</router-link>）</template>
        </span>
      </div>
      <div class="info-item">
        <span class="k">启用规则</span>
        <span class="v">
          <span v-if="enabledRules.length" class="chips">
            <span v-for="r in enabledRules" :key="r" class="chip">{{ ruleLabel(r) }}</span>
          </span>
          <span v-else class="dim">无</span>
        </span>
      </div>
      <div class="info-item">
        <span class="k">导入数据</span>
        <span class="v">
          <router-link :to="`/tasks/${task.id}/import`">导入预览</router-link>
        </span>
      </div>
      <div class="info-item">
        <span class="k">导出</span>
        <span class="v">
          <template v-if="selectedPlan">
            <a @click.prevent="exportXlsx">xlsx</a>
            ·
            <a @click.prevent="exportCsv">CSV</a>
          </template>
          <span v-else class="dim">未生成方案</span>
        </span>
      </div>
    </div>

    <section id="compute" class="section">
      <h2>算法与计算</h2>
      <p class="section-hint">勾选参与对比的算法，至少保留一个。计算完成后可在 KPI 对照中采用方案。</p>
      <div class="algos">
        <label v-for="a in ALGORITHMS" :key="a.key" class="algo">
          <input type="checkbox" :checked="algos.includes(a.key)" @change="toggleAlgo(a.key)" />
          {{ a.label }}
        </label>
      </div>
      <div class="compute-bar">
        <p v-if="canCompute.length" class="hint">{{ canCompute.join(" · ") }}</p>
        <button class="primary" @click="startCompute" :disabled="canCompute.length > 0 || showJob">
          开始计算
        </button>
      </div>
    </section>

    <JobProgress
      v-if="showJob && jobId"
      :jobId="jobId"
      :taskName="task.name"
      @done="onJobDone($event)"
      @failed="onJobFailed($event)"
    />

    <section v-if="plans.length" class="section">
      <h2>KPI 对照</h2>
      <router-link :to="`/tasks/${task.id}/kpi`" class="link">KPI 详表 →</router-link>
      <div class="table-wrap">
        <table class="kpi">
          <thead>
            <tr>
              <th>算法</th>
              <th>采用</th>
              <th>用箱数</th>
              <th>体积利用率</th>
              <th>载重利用率</th>
              <th>完成率</th>
              <th>未分配</th>
              <th>耗时s</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in plans"
              :key="p.id"
              :class="{ active: selectedPlan?.id === p.id }"
              @click="selectPlan(p)"
            >
              <td class="algo-name">{{ p.algorithm }}</td>
              <td>{{ p.is_adopted === 1 ? "是" : "" }}</td>
              <td>{{ p.kpi.overall.containers_used ?? "—" }}</td>
              <td>{{ p.kpi.overall.vol_util != null ? (p.kpi.overall.vol_util * 100).toFixed(1) + "%" : "—" }}</td>
              <td>{{ p.kpi.overall.pay_util != null ? (p.kpi.overall.pay_util * 100).toFixed(1) + "%" : "—" }}</td>
              <td>{{ p.kpi.overall.completion != null ? (p.kpi.overall.completion * 100).toFixed(1) + "%" : "—" }}</td>
              <td>{{ p.kpi.overall.unassigned_count ?? 0 }}</td>
              <td>{{ p.kpi.overall.elapsed_s != null ? p.kpi.overall.elapsed_s.toFixed(1) : "—" }}</td>
              <td>
                <button
                  class="adopt"
                  @click.stop="adopt(p)"
                  :disabled="p.is_adopted === 1"
                >
                  {{ p.is_adopted === 1 ? "已采用" : "采用" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="selectedPlan" class="section">
      <h2>3D 视图（{{ selectedPlan.algorithm }}）</h2>
      <View3D
        :containers="selectedPlan.kpi.per_container || []"
        :placements="placements"
        @select="onSelect"
      />

      <div class="table-wrap" v-if="selectedPlan.kpi.per_container?.length">
        <table class="per-kpi">
          <thead>
            <tr>
              <th>箱号</th>
              <th>件数</th>
              <th>体积利用率</th>
              <th>载重利用率</th>
              <th>顺序正确率</th>
              <th>约束满足率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in selectedPlan.kpi.per_container" :key="c.label">
              <td>{{ c.label }}</td>
              <td>{{ c.item_count }}</td>
              <td>{{ c.vol_util != null ? (c.vol_util * 100).toFixed(1) + "%" : "—" }}</td>
              <td>{{ c.pay_util != null ? (c.pay_util * 100).toFixed(1) + "%" : "—" }}</td>
              <td>
                {{ c.load_seq_correct_ratio != null ? (c.load_seq_correct_ratio * 100).toFixed(1) + "%" : "—" }}
              </td>
              <td>
                {{ c.constraint_ok_ratio != null ? (c.constraint_ok_ratio * 100).toFixed(1) + "%" : "—" }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="selected" class="section">
      <h2>选中件</h2>
      <div class="sel-card">
        <span class="pn">{{ selected.k_pn }}</span>
        <span>{{ selected.g_packmatls }}</span>
        <span>行 {{ selected.row_no }}</span>
        <span>顺序 {{ selected.load_seq ?? "—" }}</span>
        <span>{{ selected.x }}, {{ selected.y }}, {{ selected.z }}</span>
        <span>{{ selected.dim_x }}×{{ selected.dim_y }}×{{ selected.dim_z }}</span>
        <span v-if="selected.unassigned_reason" class="unassign">{{ selected.unassigned_reason }}</span>
      </div>
    </section>

    <div v-if="!plans.length && !showJob" class="empty">
      暂无方案。设置箱型后点击「开始计算」。
    </div>
  </div>

  <div v-else class="page loading">加载中…</div>
</template>

<style scoped>
.page { padding: 32px 40px; max-width: 1100px; margin: 0 auto; }
.page.loading { text-align: center; color: #999; padding-top: 80px; }
.top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.guide-card { border: 1px solid #e8e4e0; border-radius: 10px; background: #fff; padding: 16px 20px; margin-bottom: 20px; }
.guide-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.guide-head h2 { font-size: 15px; font-weight: 500; color: #2c2c2c; margin: 0; }
.guide-sub { font-size: 12px; color: #888; margin: 4px 0 0; }
.guide-pct { font-size: 20px; font-weight: 600; color: #1a5c38; }
.progress-track { height: 6px; border-radius: 3px; background: #eee9e3; margin: 12px 0 14px; overflow: hidden; }
.progress-fill { height: 100%; background: #1a5c38; border-radius: 3px; transition: width 0.3s; }
.checklist { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.check-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border: 1px solid #eee9e3; border-radius: 6px; text-decoration: none; color: #444; font-size: 13px; }
.check-item:hover { border-color: #cfdcd4; background: #fafcfb; }
.check-item.done { background: #f4f9f6; border-color: #d9e8df; }
.check-num { flex: none; width: 20px; height: 20px; border-radius: 50%; background: #eee9e3; color: #777; font-size: 11px; display: flex; align-items: center; justify-content: center; }
.check-item.done .check-num { background: #1a5c38; color: #fff; }
.check-label { flex: 1; min-width: 0; }
.check-state { flex: none; font-size: 11px; color: #999; }
.check-item.done .check-state { color: #1a5c38; }
.guide-next { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 14px; padding-top: 14px; border-top: 1px solid #f0ede8; font-size: 13px; color: #555; }
.next-btn { flex: none; padding: 6px 14px; border-radius: 4px; background: #1a5c38; color: #fff; text-decoration: none; font-size: 13px; }
.next-btn:hover { text-decoration: none; opacity: 0.9; }
.section-hint { font-size: 13px; color: #888; margin: -4px 0 12px; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
a.ghost { color: #888; text-decoration: none; font-size: 14px; }
a.ghost:hover { color: #1a5c38; }
a { color: #1a5c38; text-decoration: none; }
a:hover { text-decoration: underline; }
.error { color: #c62828; font-size: 13px; margin: 0 0 12px; }
.info-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 24px; margin-bottom: 8px; }
.info-item { display: flex; gap: 12px; font-size: 14px; min-width: 0; }
.k { color: #888; min-width: 70px; }
.v { color: #333; }
.dim { color: #999; }
.chips { display: flex; gap: 4px; flex-wrap: wrap; }
.chip { font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #f5f3f0; color: #555; }
.section { margin-top: 28px; }
h2 { font-size: 16px; font-weight: 500; color: #444; margin: 0 0 12px; }
.link { font-size: 13px; display: inline-block; margin-bottom: 12px; }
.algos { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 12px; }
.algo { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #333; cursor: pointer; }
.compute-bar { display: flex; align-items: center; gap: 12px; }
.hint { font-size: 13px; color: #888; margin: 0; }
button.primary { padding: 6px 18px; background: #1a5c38; color: #fff; border: none; border-radius: 4px; font-size: 14px; cursor: pointer; }
button.primary:disabled { opacity: 0.4; cursor: not-allowed; }
.kpi { width: 100%; border-collapse: collapse; margin-top: 8px; min-width: 760px; }
.kpi th { text-align: left; font-size: 13px; font-weight: 500; color: #888; padding: 8px 12px; border-bottom: 1px solid #e8e4e0; }
.kpi td { padding: 10px 12px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }
.kpi tr.active td { background: #f5f8f6; }
.kpi tbody tr { cursor: pointer; }
.algo-name { font-weight: 600; color: #2c2c2c; text-transform: uppercase; }
button.adopt { padding: 3px 12px; border: 1px solid #1a5c38; border-radius: 4px; background: transparent; color: #1a5c38; font-size: 12px; cursor: pointer; }
button.adopt:disabled { opacity: 0.5; cursor: default; border-color: #ccc; color: #888; }
.per-kpi { width: 100%; border-collapse: collapse; margin-top: 16px; min-width: 640px; }
.per-kpi th { text-align: left; font-size: 13px; color: #888; padding: 6px 12px; border-bottom: 1px solid #e8e4e0; }
.per-kpi td { padding: 8px 12px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }
.sel-card { display: flex; gap: 16px; align-items: center; padding: 8px 12px; background: #f9f7f4; border: 1px solid #e8e4e0; border-radius: 6px; font-size: 13px; color: #444; flex-wrap: wrap; }
.sel-card .pn { font-weight: 600; color: #1a5c38; }
.unassign { color: #c62828; }
.empty { color: #999; font-size: 14px; padding: 24px 0; text-align: center; }

@media (max-width: 900px) {
  .page { padding: 24px 24px 40px; }
  .checklist { grid-template-columns: 1fr; }
  .info-grid { grid-template-columns: 1fr; }
}

@media (max-width: 720px) {
  .page { padding: 16px 16px 32px; }
  .top { flex-direction: column; gap: 12px; }
  .guide-card { padding: 14px 14px; }
  .guide-next { flex-direction: column; align-items: stretch; }
  .next-btn { text-align: center; }
  .compute-bar { flex-wrap: wrap; }
  .sel-card { gap: 10px; }
}
</style>
