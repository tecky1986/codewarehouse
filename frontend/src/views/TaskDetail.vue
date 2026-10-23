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
} from "@/api";
import View3D from "@/components/View3D.vue";
import JobProgress from "@/components/JobProgress.vue";

const route = useRoute();
const tid = computed(() => Number(route.params.id));

const task = ref<Task | null>(null);
const plans = ref<Plan[]>([]);
const selectedPlan = ref<Plan | null>(null);
const placements = ref<Placement[]>([]);
const jobId = ref<number | null>(null);
const showJob = ref(false);
const containers = ref<ContainerType[]>([]);
const error = ref("");

const selected = ref<Placement | null>(null);
const algos = ref<string[]>(ALGORITHMS.map((a) => a.key));

const mode = computed(() => {
  if (!task.value) return null;
  try {
    const m = JSON.parse(task.value.container_mode_json || "{}");
    if (m.mode === "freemix") {
      const lock = (m.type_lock as string[]) || [];
      if (!lock.length) return null;
      return m;
    }
    const fixed = (m.fixed as Record<string, number>) || {};
    if (Object.keys(fixed).length) return m;
    if (m.type_code) return m;
    return null;
  } catch {
    return null;
  }
});

const modeSummary = computed(() => {
  if (!mode.value) return null;
  const m = mode.value as Record<string, unknown>;
  if (m.mode === "freemix") {
    const lock = (m.type_lock as string[]) || [];
    return `自由组合：${lock.join(", ")}`;
  }
  const fixed = (m.fixed as Record<string, number>) || {};
  if (Object.keys(fixed).length) {
    return Object.entries(fixed).map(([c, n]) => `${c} × ${n}`).join("  ");
  }
  if (m.type_code) return `${m.type_code} × ${m.count ?? 1}`;
  return null;
});

const enabledRules = computed(() => {
  if (!task.value?.rules_json) return [];
  try {
    const r = JSON.parse(task.value.rules_json);
    return Array.isArray(r) ? r : [];
  } catch {
    return [];
  }
});

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
    <div class="top">
      <div>
        <h1>{{ task.name }}</h1>
        <p class="sub">
          <router-link :to="`/tasks/${task.id}/import`">导入预览</router-link>
          ·
          <router-link :to="`/tasks/${task.id}/site`">Site 确认</router-link>
          ·
          <router-link :to="`/tasks/${task.id}/rules`">规则配置</router-link>
        </p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="ghost">返回</router-link>
      </div>
    </div>

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

    <section class="section">
      <h2>算法</h2>
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
    </section>

    <section v-if="selectedPlan" class="section">
      <h2>3D 视图（{{ selectedPlan.algorithm }}）</h2>
      <View3D
        :containers="selectedPlan.kpi.per_container || []"
        :placements="placements"
        @select="onSelect"
      />

      <table class="per-kpi" v-if="selectedPlan.kpi.per_container?.length">
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
.actions { display: flex; gap: 8px; }
a.ghost { color: #888; text-decoration: none; font-size: 14px; }
a.ghost:hover { color: #1a5c38; }
a { color: #1a5c38; text-decoration: none; }
a:hover { text-decoration: underline; }
.error { color: #c62828; font-size: 13px; margin: 0 0 12px; }
.info-grid { display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px; }
.info-item { display: flex; gap: 12px; font-size: 14px; }
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
.kpi { width: 100%; border-collapse: collapse; margin-top: 8px; }
.kpi th { text-align: left; font-size: 13px; font-weight: 500; color: #888; padding: 8px 12px; border-bottom: 1px solid #e8e4e0; }
.kpi td { padding: 10px 12px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }
.kpi tr.active td { background: #f5f8f6; }
.kpi tbody tr { cursor: pointer; }
.algo-name { font-weight: 600; color: #2c2c2c; text-transform: uppercase; }
button.adopt { padding: 3px 12px; border: 1px solid #1a5c38; border-radius: 4px; background: transparent; color: #1a5c38; font-size: 12px; cursor: pointer; }
button.adopt:disabled { opacity: 0.5; cursor: default; border-color: #ccc; color: #888; }
.per-kpi { width: 100%; border-collapse: collapse; margin-top: 16px; }
.per-kpi th { text-align: left; font-size: 13px; color: #888; padding: 6px 12px; border-bottom: 1px solid #e8e4e0; }
.per-kpi td { padding: 8px 12px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }
.sel-card { display: flex; gap: 16px; align-items: center; padding: 8px 12px; background: #f9f7f4; border: 1px solid #e8e4e0; border-radius: 6px; font-size: 13px; color: #444; flex-wrap: wrap; }
.sel-card .pn { font-weight: 600; color: #1a5c38; }
.unassign { color: #c62828; }
.empty { color: #999; font-size: 14px; padding: 24px 0; text-align: center; }
</style>
