<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute } from "vue-router";
import { Tasks, type Plan } from "@/api";

const route = useRoute();
const tid = ref(Number(route.params.id));

const plans = ref<Plan[]>([]);
const error = ref("");
const loading = ref(false);

const sortedPlans = computed(() =>
  [...plans.value].sort((a, b) => {
    const ka = a.kpi.overall;
    const kb = b.kpi.overall;
    if ((kb.completion || 0) !== (ka.completion || 0))
      return (kb.completion || 0) - (ka.completion || 0);
    if ((kb.containers_used || 0) !== (ka.containers_used || 0))
      return (ka.containers_used || 0) - (kb.containers_used || 0);
    return (kb.vol_util || 0) - (ka.vol_util || 0);
  }),
);

function pct(v: number | undefined): string {
  if (v == null) return "—";
  return (v * 100).toFixed(1) + "%";
}

function errorCodesText(codes?: Record<string, number> | null): string {
  if (!codes) return "";
  return Object.entries(codes)
    .map(([k, n]) => (n > 1 ? `${k}×${n}` : k))
    .join(" ");
}

function verifyText(p: Plan): string {
  const o = p.kpi.overall;
  if (o.verify_ok == null) return "—";
  if (o.verify_ok) return "通过";
  return errorCodesText(o.verify_error_codes) || "未通过";
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    plans.value = await Tasks.plans(tid.value);
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}

async function adopt(p: Plan) {
  error.value = "";
  try {
    await Tasks.adopt(tid.value, p.id);
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function exportPlan(p: Plan, fmt: "xlsx" | "csv") {
  window.open(`/api/plans/${p.id}/export?fmt=${fmt}`, "_blank");
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="top">
      <div>
        <h1>KPI 对照</h1>
        <p class="sub">多算法方案对照，按完成率 / 用箱数 / 体积利用率排序；点击「采用」指定方案。</p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="ghost">返回</router-link>
        <router-link :to="`/tasks/${tid}`" class="ghost">任务详情</router-link>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="sortedPlans.length" class="cards">
      <div
        v-for="p in sortedPlans"
        :key="p.id"
        class="kpi-card"
        :class="{ adopted: p.is_adopted === 1 }"
      >
        <div class="head">
          <span class="algo">{{ p.algorithm }}</span>
          <span v-if="p.is_adopted === 1" class="badge">已采用</span>
          <span class="ts">{{ p.created_ms ? new Date(p.created_ms).toLocaleString() : "" }}</span>
        </div>

        <div class="metrics">
          <div class="metric">
            <span class="num">{{ p.kpi.overall.containers_used ?? "—" }}</span>
            <span class="cap">用箱数</span>
          </div>
          <div class="metric">
            <span class="num">{{ pct(p.kpi.overall.vol_util) }}</span>
            <span class="cap">体积利用率</span>
          </div>
          <div class="metric">
            <span class="num">{{ pct(p.kpi.overall.pay_util) }}</span>
            <span class="cap">载重利用率</span>
          </div>
          <div class="metric">
            <span class="num">{{ pct(p.kpi.overall.completion) }}</span>
            <span class="cap">完成率</span>
          </div>
          <div class="metric">
            <span class="num">{{ pct(p.kpi.overall.constraint_ok_ratio) }}</span>
            <span class="cap">约束满足</span>
          </div>
          <div class="metric">
            <span class="num" :class="{ fail: p.kpi.overall.verify_ok === false }">{{ verifyText(p) }}</span>
            <span class="cap">校验</span>
          </div>
          <div class="metric">
            <span class="num">{{ p.kpi.overall.unassigned_count ?? 0 }}</span>
            <span class="cap">未分配</span>
          </div>
          <div class="metric">
            <span class="num">{{ p.kpi.overall.elapsed_s != null ? p.kpi.overall.elapsed_s.toFixed(1) + "s" : "—" }}</span>
            <span class="cap">耗时</span>
          </div>
        </div>
        <p v-if="p.kpi.overall.verify_ok === false" class="verify-hint">
          E102 表示当前排未填满就开了新排；砌墙 / 切割遵守行纪律。
        </p>

        <div class="foot">
          <button
            class="primary"
            @click="adopt(p)"
            :disabled="p.is_adopted === 1"
          >
            {{ p.is_adopted === 1 ? "已采用" : "采用" }}
          </button>
          <button @click="exportPlan(p, 'xlsx')" class="ghost-btn">导出 xlsx</button>
          <button @click="exportPlan(p, 'csv')" class="ghost-btn">CSV</button>
        </div>
      </div>
    </div>

    <p v-else-if="!loading" class="empty">暂无方案，请先计算。</p>
    <p v-if="loading" class="empty">加载中…</p>
  </div>
</template>

<style scoped>
.page { padding: 32px 40px; max-width: 1100px; margin: 0 auto; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; }
.actions { display: flex; gap: 8px; align-items: center; }
a.ghost { color: #888; text-decoration: none; font-size: 14px; }
a.ghost:hover { color: #1a5c38; }
.error { color: #c62828; font-size: 13px; margin: 0 0 12px; }
.cards { display: flex; flex-direction: column; gap: 16px; }
.kpi-card { border: 1px solid #e8e4e0; border-radius: 8px; padding: 16px 20px; background: #fff; }
.kpi-card.adopted { border-color: #1a5c38; }
.head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.algo { font-weight: 600; font-size: 15px; color: #2c2c2c; text-transform: uppercase; }
.badge { font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #e8f5e9; color: #1a5c38; }
.ts { font-size: 12px; color: #999; margin-left: auto; }
.metrics { display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; }
.num { font-size: 18px; font-weight: 600; color: #2c2c2c; }
.cap { font-size: 11px; color: #888; }
.fail { color: #c62828; }
.verify-hint { font-size: 12px; color: #888; margin: 10px 0 0; }
.foot { display: flex; gap: 8px; margin-top: 14px; align-items: center; }
button.primary { padding: 5px 16px; background: #1a5c38; color: #fff; border: none; border-radius: 4px; font-size: 13px; cursor: pointer; }
button.primary:disabled { opacity: 0.4; cursor: default; }
button.ghost-btn { padding: 5px 12px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 13px; cursor: pointer; color: #555; }
button.ghost-btn:hover { border-color: #1a5c38; color: #1a5c38; }
.empty { color: #999; font-size: 14px; padding: 24px 0; text-align: center; }

@media (max-width: 900px) {
  .page { padding: 24px 24px 40px; }
  .top { flex-direction: column; gap: 12px; }
  .metrics { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 720px) {
  .page { padding: 16px 16px 32px; }
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .foot { flex-wrap: wrap; }
}
</style>
