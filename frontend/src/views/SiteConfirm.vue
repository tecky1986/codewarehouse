<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute } from "vue-router";
import { Tasks, type SiteGroup } from "@/api";
import StepNav from "@/components/StepNav.vue";

const route = useRoute();
const tid = ref(Number(route.params.id));
const groups = ref<SiteGroup[]>([]);
const hasPreview = ref(false);
const siteAutoConfirmed = ref(false);
const showGuide = ref(true);
const saving = ref(false);
const saved = ref(false);
const error = ref("");
const expanded = ref<Set<number>>(new Set());

function toggleExpand(idx: number) {
  const s = new Set(expanded.value);
  if (s.has(idx)) s.delete(idx);
  else s.add(idx);
  expanded.value = s;
}

const conflict = computed(() => groups.value.some((g) => g.together && g.separate));
const stepDoneComputed = computed(
  () => hasPreview.value && (groups.value.length <= 1 || siteAutoConfirmed.value),
);
const stepDone = computed(() => {
  const done: number[] = [];
  if (hasPreview.value) done.push(1);
  if (stepDoneComputed.value) done.push(2);
  return done;
});

async function load() {
  groups.value = await Tasks.siteGroups(tid.value);
  const preview = await Tasks.preview(tid.value);
  hasPreview.value = true;
  siteAutoConfirmed.value = preview.site_auto_confirmed ?? false;
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
    await load();
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
    <StepNav :task-id="tid" :current="2" :done="stepDone" />

    <div class="top">
      <div>
        <h1>Site 确认</h1>
        <p class="sub">按站点列出货；默认不勾选。同柜与分离互斥。</p>
      </div>
      <div class="actions">
        <router-link to="/tasks" class="ghost">返回任务列表</router-link>
        <button class="primary" @click="save" :disabled="saving || conflict || stepDoneComputed">
          {{ saving ? "保存中…" : "保存" }}
        </button>
      </div>
    </div>

    <div v-if="showGuide" class="guide-bar">
      <div class="guide-text">
        <strong>配置指引 · 第 2 步</strong>
        <span>按 Site 选择同柜或分离。只有 1 个 Site（或未填）时本步自动完成，可直接进入规则配置。</span>
      </div>
      <button class="guide-close" @click="showGuide = false">知道了</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="ok">已保存</p>
    <p v-if="stepDoneComputed" class="ok">当前数据只有 1 个 Site（或未填 Site），本步骤已自动完成，可直接进入规则配置。</p>

      <div v-if="groups.length === 0" class="empty">暂无 Site 数据（请先导入）</div>

    <div v-for="(g, idx) in groups" :key="idx" class="card">
      <div class="card-head" @click="toggleExpand(idx)">
        <div class="card-head-left">
          <span class="chevron" :class="{ open: expanded.has(idx) }">▶</span>
          <span class="site-name">{{ g.site || "（未填 Site）" }}</span>
          <span class="count">{{ g.items.length }} 件</span>
        </div>
        <div class="card-head-right">
          <span v-if="g.together" class="tag tag-together">同柜</span>
          <span v-else-if="g.separate" class="tag tag-separate">分离</span>
          <span v-else class="tag tag-none">未设</span>
        </div>
      </div>

      <template v-if="expanded.has(idx)">
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

        <div class="table-wrap">
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
      </template>
    </div>

    <div class="next-bar">
      <span>{{
        stepDoneComputed ? "Site 确认已自动完成，继续配置规则即可。" : saved ? "Site 设置已保存。" : "保存后继续配置规则。"
      }}</span>
      <router-link :to="`/tasks/${tid}/rules`" class="next-btn">
        下一步：规则配置
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.guide-bar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid #d9e8df; background: #f4f9f6; border-radius: 8px; margin-bottom: 16px; }
.guide-text { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #436652; line-height: 1.6; }
.guide-text strong { font-size: 13px; color: #1a5c38; }
.guide-close { flex: none; padding: 4px 12px; border: 1px solid #b9d2c4; border-radius: 4px; background: #fff; color: #1a5c38; font-size: 12px; cursor: pointer; }
.page { padding: 32px 40px; max-width: 900px; margin: 0 auto; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; }
.actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.next-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 24px; padding: 14px 16px; border: 1px solid #e8e4e0; background: #fff; border-radius: 8px; font-size: 13px; color: #555; }
.next-btn { flex: none; padding: 7px 16px; border-radius: 4px; background: #1a5c38; color: #fff; text-decoration: none; font-size: 13px; }
.next-btn:hover { text-decoration: none; opacity: 0.9; }
button.primary { padding: 6px 18px; background: #1a5c38; color: #fff; border: none; border-radius: 4px; font-size: 14px; cursor: pointer; }
button.primary:disabled { opacity: 0.5; }
a.ghost { color: #888; text-decoration: none; font-size: 14px; }
.empty { color: #999; padding: 24px 0; text-align: center; font-size: 14px; }
.error { color: #c62828; font-size: 13px; margin: 0 0 8px; }
.ok { color: #1a5c38; font-size: 13px; margin: 0 0 8px; }
.card { border: 1px solid #e8e4e0; border-radius: 8px; padding: 14px 20px; margin-bottom: 12px; background: #fff; }
.card-head { display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }
.card-head-left { display: flex; align-items: center; gap: 8px; }
.card-head-right { display: flex; align-items: center; gap: 6px; }
.chevron { font-size: 10px; color: #999; transition: transform 0.15s; }
.chevron.open { transform: rotate(90deg); }
.site-name { font-weight: 600; font-size: 15px; color: #2c2c2c; }
.count { font-size: 13px; color: #888; }
.tag { font-size: 11px; padding: 1px 8px; border-radius: 3px; }
.tag-together { background: #e8f5e9; color: #1a5c38; }
.tag-separate { background: #fff8e1; color: #8a6d1b; }
.tag-none { background: #f0ede8; color: #999; }
.opts { display: flex; gap: 20px; margin-bottom: 12px; }
.opts label { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #333; cursor: pointer; }
.mini { width: 100%; border-collapse: collapse; min-width: 520px; }
.mini th { text-align: left; font-size: 12px; color: #888; font-weight: 500; padding: 4px 8px; border-bottom: 1px solid #e8e4e0; }
.mini td { padding: 6px 8px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }

@media (max-width: 900px) {
  .page { padding: 24px 24px 40px; }
  .top { flex-direction: column; gap: 12px; }
}

@media (max-width: 720px) {
  .page { padding: 16px 16px 32px; }
  .card { padding: 14px; }
  .next-bar { flex-direction: column; align-items: stretch; gap: 10px; }
  .next-btn { text-align: center; }
}
</style>
