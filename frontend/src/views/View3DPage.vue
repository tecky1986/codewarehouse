<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import {
  Tasks,
  Plans,
  type Plan,
  type Placement,
} from "@/api";
import View3D from "@/components/View3D.vue";

const route = useRoute();
const tid = ref(Number(route.params.id));

const plans = ref<Plan[]>([]);
const selectedPlan = ref<Plan | null>(null);
const placements = ref<Placement[]>([]);
const error = ref("");

async function load() {
  error.value = "";
  try {
    plans.value = await Tasks.plans(tid.value);
    const adopted =
      plans.value.find((p) => p.is_adopted === 1) || plans.value[0];
    selectedPlan.value = adopted || null;
    if (selectedPlan.value) {
      placements.value = await Plans.placements(selectedPlan.value.id);
    }
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function selectPlan(p: Plan) {
  selectedPlan.value = p;
  placements.value = await Plans.placements(p.id);
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="top">
      <div>
        <h1>3D 视图</h1>
        <p class="sub">每箱独立视图 · 选中居中工作区 · 0.5/1/2/4 倍速回放 · 点选高亮</p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="ghost">返回</router-link>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="plans.length" class="plan-row">
      <button
        v-for="p in plans"
        :key="p.id"
        :class="['plan-btn', { active: selectedPlan?.id === p.id }]"
        @click="selectPlan(p)"
      >
        {{ p.algorithm }}
        <span v-if="p.is_adopted === 1" class="badge">采用</span>
      </button>
    </div>

    <View3D
      v-if="selectedPlan"
      :containers="selectedPlan.kpi.per_container || []"
      :placements="placements"
    />

    <p v-else-if="!error" class="empty">暂无方案，请先计算。</p>
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
.plan-row { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.plan-btn { padding: 6px 16px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 14px; cursor: pointer; color: #333; display: flex; align-items: center; gap: 6px; }
.plan-btn.active { background: #1a5c38; color: #fff; border-color: #1a5c38; }
.badge { font-size: 10px; padding: 0 5px; border-radius: 3px; background: #e8f5e9; color: #1a5c38; }
.plan-btn.active .badge { background: rgba(255,255,255,0.3); color: #fff; }
.empty { color: #999; font-size: 14px; padding: 24px 0; text-align: center; }

@media (max-width: 900px) {
  .page { padding: 24px 24px 40px; }
  .top { flex-direction: column; gap: 12px; }
}

@media (max-width: 720px) {
  .page { padding: 16px 16px 32px; }
}
</style>
