<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  taskId?: number | null;
  doneSteps?: number[];
}>();

const STEPS = [
  { n: 1, label: "新建任务", hint: "输入任务名称，点击「新建并配置」" },
  { n: 2, label: "导入 Excel", hint: "上传货物明细表，确认列映射" },
  { n: 3, label: "设置箱型与规则", hint: "选择集装箱型号，配置装箱规则" },
  { n: 4, label: "计算并导出", hint: "运行算法，对比 KPI，导出方案" },
];

const isTaskCreated = computed(() => !!props.taskId);
const doneSet = computed(() => new Set(props.doneSteps || []));

function stepState(n: number): "done" | "active" | "pending" {
  if (doneSet.value.has(n)) return "done";
  if (n === 1 && !isTaskCreated.value) return "active";
  if (n === 2 && isTaskCreated.value && !doneSet.value.has(2)) return "active";
  if (n === 3 && isTaskCreated.value && !doneSet.value.has(3)) return "active";
  if (n === 4 && isTaskCreated.value && !doneSet.value.has(4)) return "active";
  return "pending";
}
</script>

<template>
  <div class="guide">
    <div class="guide-head">
      <strong>首次使用引导</strong>
      <span class="hint">按 4 步完成一次完整装箱流程</span>
    </div>
    <div class="steps">
      <div
        v-for="s in STEPS"
        :key="s.n"
        class="step"
        :class="stepState(s.n)"
      >
        <span class="num">{{ s.n }}</span>
        <div class="body">
          <span class="label">{{ s.label }}</span>
          <span class="desc">{{ s.hint }}</span>
        </div>
        <span v-if="stepState(s.n) === 'done'" class="tick">✓</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.guide {
  border: 1px solid #d9e8df;
  background: #f4f9f6;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;
}
.guide-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.guide-head strong {
  font-size: 13px;
  color: #1a5c38;
}
.hint {
  font-size: 12px;
  color: #436652;
}
.steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
@media (max-width: 600px) {
  .steps {
    grid-template-columns: repeat(2, 1fr);
  }
}
.step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #e8e4e0;
}
.step.active {
  border-color: #1a5c38;
  background: #e8f5ee;
}
.step.done {
  opacity: 0.7;
  border-color: #c2d8cc;
}
.step.pending {
  opacity: 0.55;
}
.num {
  flex: none;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #1a5c38;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.step.done .num {
  background: #6a9d82;
}
.body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.label {
  font-size: 13px;
  font-weight: 500;
  color: #2c2c2c;
}
.desc {
  font-size: 11px;
  color: #666;
}
.tick {
  flex: none;
  font-size: 12px;
  color: #1a5c38;
}
</style>
