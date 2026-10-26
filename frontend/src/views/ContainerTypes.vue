<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ContainerTypes, type ContainerType } from "@/api";

const items = ref<ContainerType[]>([]);
const showForm = ref(false);
const editing = ref<ContainerType | null>(null);
const error = ref("");

const emptyForm = () => ({
  code: "",
  name: "",
  iso_code: "",
  inner_l: 5900,
  inner_w: 2350,
  inner_h: 2390,
  door_w: 2340,
  door_h: 2280,
  max_payload: 28200,
  tare_weight: 0,
  freight_price: 0,
  enabled: 1,
  remark: "",
});

const form = ref(emptyForm());

async function load() {
  error.value = "";
  try {
    items.value = await ContainerTypes.list();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function startCreate() {
  editing.value = null;
  form.value = emptyForm();
  showForm.value = true;
}

function startEdit(t: ContainerType) {
  editing.value = t;
  form.value = {
    code: t.code,
    name: t.name,
    iso_code: t.iso_code || "",
    inner_l: t.inner_l,
    inner_w: t.inner_w,
    inner_h: t.inner_h,
    door_w: t.door_w ?? 0,
    door_h: t.door_h ?? 0,
    max_payload: t.max_payload,
    tare_weight: t.tare_weight ?? 0,
    freight_price: t.freight_price ?? 0,
    enabled: t.enabled ?? 1,
    remark: t.remark || "",
  };
  showForm.value = true;
}

async function save() {
  error.value = "";
  try {
    if (editing.value) {
      await ContainerTypes.update(editing.value.id, form.value);
    } else {
      await ContainerTypes.create(form.value);
    }
    showForm.value = false;
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function remove(t: ContainerType) {
  if (!confirm(`删除箱型 ${t.code}？`)) return;
  error.value = "";
  try {
    await ContainerTypes.remove(t.id);
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function vol(t: ContainerType): string {
  const v = t.volume;
  if (v) return v.toFixed(1);
  return (t.inner_l * t.inner_w * t.inner_h / 1e9).toFixed(1);
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="top">
      <div>
        <h1>箱型库</h1>
        <p class="sub">预置 20GP / 40GP / 40HQ；被任务引用后禁止删除。</p>
      </div>
      <div class="actions">
        <button class="primary" @click="startCreate">新增箱型</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="showForm" class="form-card">
      <h2>{{ editing ? `编辑 ${editing.code}` : "新增箱型" }}</h2>
      <div class="grid">
        <label>代码 <input v-model="form.code" :disabled="!!editing" /></label>
        <label>名称 <input v-model="form.name" /></label>
        <label>ISO 代码 <input v-model="form.iso_code" /></label>
        <label>内长mm <input type="number" v-model.number="form.inner_l" /></label>
        <label>内宽mm <input type="number" v-model.number="form.inner_w" /></label>
        <label>内高mm <input type="number" v-model.number="form.inner_h" /></label>
        <label>门宽mm <input type="number" v-model.number="form.door_w" /></label>
        <label>门高mm <input type="number" v-model.number="form.door_h" /></label>
        <label>最大载重kg <input type="number" v-model.number="form.max_payload" /></label>
        <label>箱自重kg <input type="number" v-model.number="form.tare_weight" /></label>
        <label>单箱运费 <input type="number" step="0.01" v-model.number="form.freight_price" /></label>
        <label class="enb">启用 <input type="checkbox" v-model="form.enabled" :true-value="1" :false-value="0" /></label>
        <label class="wide">备注 <input v-model="form.remark" /></label>
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
            <th>代码</th>
            <th>名称</th>
            <th>内长×宽×高 mm</th>
            <th>容积m³</th>
            <th>最大载重kg</th>
            <th>单箱运费</th>
            <th>状态</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in items" :key="t.id">
            <td class="code">{{ t.code }}</td>
            <td>{{ t.name }}</td>
            <td>{{ t.inner_l }}×{{ t.inner_w }}×{{ t.inner_h }}</td>
            <td>{{ vol(t) }}</td>
            <td>{{ t.max_payload }}</td>
            <td>{{ t.freight_price != null ? t.freight_price : "—" }}</td>
            <td>{{ t.enabled ? "启用" : "停用" }}</td>
            <td class="ops">
              <button @click="startEdit(t)">编辑</button>
              <button @click="remove(t)" class="danger">删除</button>
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
.grid label.wide { grid-column: span 2; }
.grid label.enb { flex-direction: row; align-items: center; gap: 8px; }
.grid input { padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
.grid label.enb input { padding: 0; }
.form-actions { display: flex; gap: 8px; margin-top: 14px; }
.form-actions button { padding: 6px 16px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 14px; cursor: pointer; }
.tbl { width: 100%; border-collapse: collapse; min-width: 720px; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.tbl th { text-align: left; font-size: 13px; color: #888; font-weight: 500; padding: 8px 12px; border-bottom: 1px solid #e8e4e0; }
.tbl td { padding: 10px 12px; font-size: 14px; color: #333; border-bottom: 1px solid #f0ede8; }
.tbl .code { font-weight: 600; color: #1a5c38; }
.ops { display: flex; gap: 6px; }
.ops button { padding: 3px 10px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 12px; cursor: pointer; }
.ops button.danger { color: #c62828; border-color: #c62828; }

@media (max-width: 900px) {
  .page { padding: 24px 24px 40px; }
  .top { flex-direction: column; gap: 12px; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .grid label.wide { grid-column: span 2; }
}

@media (max-width: 720px) {
  .page { padding: 16px 16px 32px; }
  .grid { grid-template-columns: 1fr; }
  .grid label.wide { grid-column: span 1; }
}
</style>
