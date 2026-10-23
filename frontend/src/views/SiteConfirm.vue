<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute } from "vue-router";
import { Tasks, type SiteGroup } from "@/api";

const route = useRoute();
const tid = ref(Number(route.params.id));
const groups = ref<SiteGroup[]>([]);
const saving = ref(false);
const saved = ref(false);
const error = ref("");

const conflict = computed(() => groups.value.some((g) => g.together && g.separate));

async function load() {
  groups.value = await Tasks.siteGroups(tid.value);
}

function toggleTogether(g: SiteGroup, val: boolean) {
  g.together = val;
  if (val) g.separate = false;
  saved.value = false;
}

function toggleSeparate(g: SiteGroup, val: boolean) {
  g.separate = val;
  if (val) g.together = false;
  saved.value = false;
}

async function save() {
  saving.value = true;
  error.value = "";
  try {
    await Tasks.saveSiteGroups(tid.value, groups.value);
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
        <h1>Site 确认</h1>
        <p class="sub">按站点列出货；默认不勾选。同柜与分离互斥。</p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="ghost">返回</router-link>
        <button class="primary" @click="save" :disabled="saving || conflict">保存</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="ok">已保存</p>

    <div v-if="groups.length === 0" class="empty">暂无 Site 数据（请先导入）</div>

    <div v-for="g in groups" :key="g.site || '_blank'" class="card">
      <div class="card-head">
        <span class="site-name">{{ g.site || "（未填 Site）" }}</span>
        <span class="count">{{ g.items.length }} 件</span>
      </div>

      <div class="opts">
        <label>
          <input
            type="checkbox"
            :checked="g.together"
            @change="(e) => toggleTogether(g, (e.target as HTMLInputElement).checked)"
          />
          同柜
        </label>
        <label>
          <input
            type="checkbox"
            :checked="g.separate"
            @change="(e) => toggleSeparate(g, (e.target as HTMLInputElement).checked)"
          />
          分离
        </label>
      </div>

      <table class="mini">
        <thead>
          <tr>
            <th>行</th>
            <th>OUTCASE</th>
            <th>PackMatls</th>
            <th>体积m³</th>
            <th>毛重kg</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in g.items" :key="it.row_no">
            <td>{{ it.row_no }}</td>
            <td>{{ it.outcase }}</td>
            <td>{{ it.packmatls }}</td>
            <td>{{ it.volume ? it.volume.toFixed(3) : "—" }}</td>
            <td>{{ it.gross ?? "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px 40px; max-width: 900px; margin: 0 auto; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; }
.actions { display: flex; gap: 8px; align-items: center; }
button.primary { padding: 6px 18px; background: #1a5c38; color: #fff; border: none; border-radius: 4px; font-size: 14px; cursor: pointer; }
button.primary:disabled { opacity: 0.5; }
a.ghost { color: #888; text-decoration: none; font-size: 14px; }
.empty { color: #999; padding: 24px 0; text-align: center; font-size: 14px; }
.error { color: #c62828; font-size: 13px; margin: 0 0 8px; }
.ok { color: #1a5c38; font-size: 13px; margin: 0 0 8px; }
.card { border: 1px solid #e8e4e0; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; background: #fff; }
.card-head { display: flex; justify-content: space-between; margin-bottom: 10px; }
.site-name { font-weight: 600; font-size: 15px; color: #2c2c2c; }
.count { font-size: 13px; color: #888; }
.opts { display: flex; gap: 20px; margin-bottom: 12px; }
.opts label { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #333; cursor: pointer; }
.mini { width: 100%; border-collapse: collapse; }
.mini th { text-align: left; font-size: 12px; color: #888; font-weight: 500; padding: 4px 8px; border-bottom: 1px solid #e8e4e0; }
.mini td { padding: 6px 8px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }
</style>
