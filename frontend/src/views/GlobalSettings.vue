<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Settings } from "@/api";

const fields = ref<Record<string, string>>({});
const saving = ref(false);
const saved = ref(false);
const error = ref("");

const FIELDS = [
  { key: "manual_limit_kg", label: "人工搬运上限", unit: "kg" },
  { key: "fork_tine_mm", label: "叉车铲齿长度", unit: "mm" },
  { key: "time_limit_s", label: "算法计算时限", unit: "s" },
  { key: "gap_mm", label: "货物间隙", unit: "mm" },
];

async function load() {
  fields.value = await Settings.get();
}

async function save() {
  saving.value = true;
  saved.value = false;
  error.value = "";
  try {
    const body: Record<string, unknown> = {};
    for (const f of FIELDS) {
      const v = fields.value[f.key];
      if (v !== undefined) body[f.key] = Number(v);
    }
    fields.value = await Settings.put(body);
    saved.value = true;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="top">
      <div>
        <h1>全局参数</h1>
        <p class="sub">对全部任务生效；>30 kg 强制叉车，铲齿 1220 mm，时限 60 s。</p>
      </div>
      <div class="actions">
        <button class="primary" @click="save" :disabled="saving">保存</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="ok">已保存</p>

    <div class="card">
      <label v-for="f in FIELDS" :key="f.key" class="field">
        <span class="lbl">{{ f.label }}（{{ f.unit }}）</span>
        <input
          v-model="fields[f.key]"
          type="number"
          :disabled="!Object.keys(fields).length"
        />
      </label>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px 40px; max-width: 600px; margin: 0 auto; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; }
button.primary { padding: 6px 18px; background: #1a5c38; color: #fff; border: none; border-radius: 4px; font-size: 14px; cursor: pointer; }
button.primary:disabled { opacity: 0.5; }
.error { color: #c62828; font-size: 13px; margin: 0 0 8px; }
.ok { color: #1a5c38; font-size: 13px; margin: 0 0 8px; }
.card { border: 1px solid #e8e4e0; border-radius: 8px; padding: 20px; background: #fff; }
.field { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 13px; color: #555; margin-bottom: 14px; }
.field:last-child { margin-bottom: 0; }
.lbl { flex: 1; }
.field input { width: 120px; padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; text-align: right; }

@media (max-width: 720px) {
  .page { padding: 16px 16px 32px; }
  .top { flex-direction: column; gap: 12px; }
  .card { padding: 14px; }
  .field { flex-wrap: wrap; }
  .field input { width: 100%; max-width: 180px; }
}
</style>
