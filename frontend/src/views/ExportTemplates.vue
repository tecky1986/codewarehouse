<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
  ExportTemplates,
  templateColumns,
  type ExportTemplate,
  type ExportColumn,
} from "@/api";

const DEFAULT_COLUMNS: ExportColumn[] = [
  { field: "a_no", header: "编号", width: 10 },
  { field: "b_len", header: "长cm", width: 8 },
  { field: "c_wid", header: "宽cm", width: 8 },
  { field: "d_hgt", header: "高cm", width: 8 },
  { field: "e_cbm", header: "CBM", width: 8 },
  { field: "f_outcase", header: "OUTCASE", width: 14 },
  { field: "g_packmatls", header: "PackMatls", width: 14 },
  { field: "h_tare", header: "箱重kg", width: 8 },
  { field: "i_net", header: "净重kg", width: 8 },
  { field: "j_gross", header: "毛重kg", width: 8 },
  { field: "k_pn", header: "PN", width: 12 },
  { field: "l_note", header: "备注", width: 20 },
  { field: "m_site", header: "Site", width: 12 },
  { field: "label", header: "箱号", width: 10 },
  { field: "load_seq", header: "装箱顺序", width: 10 },
  { field: "o_ref", header: "REF", width: 12 },
  { field: "p_dn", header: "DN", width: 12 },
  { field: "q_misc", header: "其他", width: 14 },
];

const templates = ref<ExportTemplate[]>([]);
const showForm = ref(false);
const editing = ref<ExportTemplate | null>(null);
const formName = ref("");
const formCols = ref<ExportColumn[]>([]);
const saving = ref(false);
const error = ref("");

async function load() {
  error.value = "";
  try {
    templates.value = await ExportTemplates.list();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

function startCreate() {
  editing.value = null;
  formName.value = "";
  formCols.value = JSON.parse(JSON.stringify(DEFAULT_COLUMNS));
  showForm.value = true;
}

function startEdit(t: ExportTemplate) {
  editing.value = t;
  formName.value = t.name;
  formCols.value = templateColumns(t).length
    ? (templateColumns(t) as ExportColumn[])
    : JSON.parse(JSON.stringify(DEFAULT_COLUMNS));
  showForm.value = true;
}

function colHeader(c: ExportColumn): string {
  return c.header || c.field || "";
}

async function save() {
  saving.value = true;
  error.value = "";
  try {
    if (editing.value) {
      await ExportTemplates.update(editing.value.id, {
        name: formName.value,
        columns: formCols.value,
      });
    } else {
      await ExportTemplates.create(formName.value, formCols.value);
    }
    showForm.value = false;
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    saving.value = false;
  }
}

async function remove(t: ExportTemplate) {
  if (t.is_default) {
    error.value = "默认模板不可删除";
    return;
  }
  if (!confirm(`删除模板「${t.name}」？`)) return;
  error.value = "";
  try {
    await ExportTemplates.remove(t.id);
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function markDefault(t: ExportTemplate) {
  error.value = "";
  try {
    await ExportTemplates.update(t.id, { name: t.name, is_default: 1 });
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
        <h1>导出模板</h1>
        <p class="sub">控制导出 xlsx 的列字段、顺序、列宽与对齐；默认模板不可删除。</p>
      </div>
      <div class="actions">
        <button class="primary" @click="startCreate">新增模板</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="showForm" class="form-card">
      <h2>{{ editing ? `编辑模板` : "新增模板" }}</h2>
      <label class="field">名称 <input v-model="formName" /></label>
      <div class="cols">
        <div v-for="(c, i) in formCols" :key="i" class="col-row">
          <input v-model="c.field" class="fld" placeholder="field" />
          <input v-model="c.header" class="hdr" placeholder="表头" />
          <input v-model.number="c.width" class="w" type="number" placeholder="列宽" />
          <select v-model="c.align">
            <option value="">对齐</option>
            <option value="left">左</option>
            <option value="center">中</option>
            <option value="right">右</option>
          </select>
          <button @click="formCols.splice(i, 1)" class="rm">×</button>
        </div>
      </div>
      <button class="add-col" @click="formCols.push({ field: '', header: '' })">添加列</button>
      <div class="form-actions">
        <button class="primary" @click="save" :disabled="saving">保存</button>
        <button @click="showForm = false">取消</button>
      </div>
    </div>

    <div v-for="t in templates" :key="t.id" class="card">
      <div class="card-head">
        <span class="name">
          {{ t.name }}
          <span v-if="t.is_default" class="badge">默认</span>
        </span>
        <div class="ops">
          <button @click="markDefault(t)" :disabled="!!t.is_default">设为默认</button>
          <button @click="startEdit(t)">编辑</button>
          <button @click="remove(t)" class="danger" :disabled="!!t.is_default">删除</button>
        </div>
      </div>
      <div class="col-preview" v-if="templateColumns(t).length">
        <span v-for="(c, i) in templateColumns(t)" :key="i" class="col-chip">
          {{ colHeader(c) }}
        </span>
      </div>
    </div>

    <p v-if="templates.length === 0" class="empty">暂无模板</p>
  </div>
</template>

<style scoped>
.page { padding: 32px 40px; max-width: 900px; margin: 0 auto; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 500; color: #2c2c2c; margin: 0; }
.sub { font-size: 13px; color: #888; margin: 6px 0 0; }
button.primary { padding: 6px 18px; background: #1a5c38; color: #fff; border: none; border-radius: 4px; font-size: 14px; cursor: pointer; }
button.primary:disabled { opacity: 0.5; }
.error { color: #c62828; font-size: 13px; margin: 0 0 12px; }
.form-card { border: 1px solid #e8e4e0; border-radius: 8px; padding: 16px 20px; margin-bottom: 24px; background: #fff; }
.form-card h2 { font-size: 15px; font-weight: 500; color: #444; margin: 0 0 12px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #555; margin-bottom: 10px; }
.field input { padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
.cols { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.col-row { display: flex; gap: 6px; align-items: center; }
.col-row .fld { flex: 2; padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; }
.col-row .hdr { flex: 2; padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; }
.col-row .w { width: 70px; padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; }
.col-row select { padding: 4px 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; }
.col-row .rm { border: none; background: none; color: #c62828; cursor: pointer; font-size: 14px; }
.add-col { font-size: 13px; color: #1a5c38; background: none; border: none; cursor: pointer; padding: 4px 0; margin-bottom: 10px; }
.form-actions { display: flex; gap: 8px; margin-top: 14px; }
.form-actions button { padding: 6px 16px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 14px; cursor: pointer; }
.card { border: 1px solid #e8e4e0; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; background: #fff; }
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.name { font-weight: 500; font-size: 15px; color: #2c2c2c; }
.badge { font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #e8f5e9; color: #1a5c38; margin-left: 6px; }
.ops { display: flex; gap: 6px; }
.ops button { padding: 3px 10px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 12px; cursor: pointer; }
.ops button.danger { color: #c62828; border-color: #c62828; }
.ops button:disabled { opacity: 0.3; cursor: not-allowed; }
.col-preview { display: flex; flex-wrap: wrap; gap: 6px; }
.col-chip { font-size: 12px; padding: 2px 8px; background: #f5f3f0; border-radius: 3px; color: #555; }
.empty { color: #999; font-size: 14px; padding: 24px 0; text-align: center; }
</style>
