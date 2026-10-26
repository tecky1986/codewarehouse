<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Packages, type PackageMaster } from "@/api";

const items = ref<PackageMaster[]>([]);
const showForm = ref(false);
const editing = ref<PackageMaster | null>(null);
const error = ref("");

const emptyForm = () => ({
  pn: "",
  name: "",
  package_type: "",
  cargo_type: "",
  l: 0,
  w: 0,
  h: 0,
  tare: 0,
  net: 0,
  gross: 0,
  rotatable: 1,
  crush_sensitive: 0,
  same_type_stack: 0,
  default_loading: "人工",
  max_stack: 0,
  enabled: 1,
});

const form = ref(emptyForm());

async function load() {
  error.value = "";
  try {
    items.value = await Packages.list();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function startCreate() {
  editing.value = null;
  form.value = emptyForm();
  showForm.value = true;
}

function startEdit(p: PackageMaster) {
  editing.value = p;
  form.value = {
    pn: p.pn || "",
    name: p.name || "",
    package_type: p.package_type || "",
    cargo_type: p.cargo_type || "",
    l: p.l ?? 0,
    w: p.w ?? 0,
    h: p.h ?? 0,
    tare: p.tare ?? 0,
    net: p.net ?? 0,
    gross: p.gross ?? 0,
    rotatable: p.rotatable ?? 1,
    crush_sensitive: p.crush_sensitive ?? 0,
    same_type_stack: p.same_type_stack ?? 0,
    default_loading: p.default_loading || "人工",
    max_stack: p.max_stack ?? 0,
    enabled: p.enabled ?? 1,
  };
  showForm.value = true;
}

async function save() {
  error.value = "";
  try {
    const body = { ...form.value, pn: form.value.pn || null, name: form.value.name || null };
    if (editing.value) {
      await Packages.update(editing.value.id, body);
    } else {
      await Packages.create(body);
    }
    showForm.value = false;
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function remove(p: PackageMaster) {
  if (!confirm(`删除包装 ${p.pn || p.name}？`)) return;
  error.value = "";
  try {
    await Packages.remove(p.id);
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="top">
      <div>
        <h1>包装主数据</h1>
        <p class="sub">PN 优先键，PackMatls 次级键；尺寸 mm、重量 kg。</p>
      </div>
      <div class="actions">
        <button class="primary" @click="startCreate">新增</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="showForm" class="form-card">
      <h2>{{ editing ? `编辑 ${editing.pn || editing.name}` : "新增包装" }}</h2>
      <div class="grid">
        <label>PN <input v-model="form.pn" :disabled="!!editing" /></label>
        <label>PackMatls <input v-model="form.name" /></label>
        <label>包装类型 <input v-model="form.package_type" /></label>
        <label>货物类型 <input v-model="form.cargo_type" /></label>
        <label>长mm <input type="number" v-model.number="form.l" /></label>
        <label>宽mm <input type="number" v-model.number="form.w" /></label>
        <label>高mm <input type="number" v-model.number="form.h" /></label>
        <label>箱重kg <input type="number" step="0.1" v-model.number="form.tare" /></label>
        <label>净重kg <input type="number" step="0.1" v-model.number="form.net" /></label>
        <label>毛重kg <input type="number" step="0.1" v-model.number="form.gross" /></label>
        <label class="ck">可旋转 <input type="checkbox" v-model="form.rotatable" :true-value="1" :false-value="0" /></label>
        <label class="ck">易压 <input type="checkbox" v-model="form.crush_sensitive" :true-value="1" :false-value="0" /></label>
        <label class="ck">同种堆叠 <input type="checkbox" v-model="form.same_type_stack" :true-value="1" :false-value="0" /></label>
        <label>默认装卸
          <select v-model="form.default_loading">
            <option>人工</option>
            <option>叉车</option>
          </select>
        </label>
        <label>最大堆码层数 <input type="number" v-model.number="form.max_stack" /></label>
        <label class="ck">启用 <input type="checkbox" v-model="form.enabled" :true-value="1" :false-value="0" /></label>
      </div>
      <div class="form-actions">
        <button class="primary" @click="save">保存</button>
        <button @click="showForm = false">取消</button>
      </div>
    </div>

    <div class="table-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>PN</th>
            <th>PackMatls</th>
            <th>尺寸 mm</th>
            <th>箱重</th>
            <th>净重</th>
            <th>毛重</th>
            <th>属性</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in items" :key="p.id">
            <td class="pn">{{ p.pn }}</td>
            <td>{{ p.name }}</td>
            <td>{{ p.l }}×{{ p.w }}×{{ p.h }}</td>
            <td>{{ p.tare }}</td>
            <td>{{ p.net }}</td>
            <td>{{ p.gross }}</td>
            <td class="attrs">
              <span v-if="p.crush_sensitive">易压</span>
              <span v-if="p.same_type_stack">同种堆叠</span>
              <span v-if="!p.rotatable">{{ p.rotatable === 0 ? "不可旋转" : "可旋转" }}</span>
              <span>{{ p.default_loading }}</span>
            </td>
            <td class="ops">
              <button @click="startEdit(p)">编辑</button>
              <button @click="remove(p)" class="danger">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px 40px; max-width: 980px; margin: 0 auto; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; }
button.primary { padding: 6px 18px; background: #1a5c38; color: #fff; border: none; border-radius: 4px; font-size: 14px; cursor: pointer; }
.error { color: #c62828; font-size: 13px; margin: 0 0 12px; }
.form-card { border: 1px solid #e8e4e0; border-radius: 8px; padding: 16px 20px; margin-bottom: 24px; background: #fff; }
.form-card h2 { font-size: 15px; font-weight: 500; color: #444; margin: 0 0 12px; }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.grid label { font-size: 13px; color: #555; display: flex; flex-direction: column; gap: 4px; }
.grid label.ck { flex-direction: row; align-items: center; gap: 8px; }
.grid input { padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
.grid label.ck input { padding: 0; }
.grid select { padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
.form-actions { display: flex; gap: 8px; margin-top: 14px; }
.form-actions button { padding: 6px 16px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 14px; cursor: pointer; }
.tbl { width: 100%; border-collapse: collapse; min-width: 760px; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.tbl th { text-align: left; font-size: 13px; color: #888; font-weight: 500; padding: 8px 12px; border-bottom: 1px solid #e8e4e0; }
.tbl td { padding: 10px 12px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }
.tbl .pn { font-weight: 600; color: #1a5c38; }
.attrs { display: flex; gap: 6px; flex-wrap: wrap; }
.attrs span { font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #f5f3f0; color: #555; }
.ops { display: flex; gap: 6px; }
.ops button { padding: 3px 10px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 12px; cursor: pointer; }
.ops button.danger { color: #c62828; border-color: #c62828; }

@media (max-width: 900px) {
  .page { padding: 24px 24px 40px; }
  .top { flex-direction: column; gap: 12px; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 720px) {
  .page { padding: 16px 16px 32px; }
  .grid { grid-template-columns: 1fr; }
}
</style>
