<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  taskId: number;
  current: number;
  done?: number[];
}>();

const steps = computed(() => [
  {
    n: 1,
    label: "数据与箱型",
    hint: "导入 xlsx，设置箱型",
    to: `/tasks/${props.taskId}/import`,
  },
  {
    n: 2,
    label: "Site 确认",
    hint: "按站点选择同柜或分离",
    to: `/tasks/${props.taskId}/site`,
  },
  {
    n: 3,
    label: "规则配置",
    hint: "启用规则并调整优先级",
    to: `/tasks/${props.taskId}/rules`,
  },
  {
    n: 4,
    label: "计算与结果",
    hint: "开始计算，查看 KPI 与 3D",
    to: `/tasks/${props.taskId}`,
  },
]);

function state(n: number): "active" | "done" | "todo" {
  if (props.current === n) return "active";
  if (props.done?.includes(n)) return "done";
  return "todo";
}
</script>

<template>
  <nav class="step-nav" aria-label="任务配置进度">
    <router-link
      v-for="s in steps"
      :key="s.n"
      :to="s.to"
      class="step"
      :class="state(s.n)"
    >
      <span class="num">{{ s.n }}</span>
      <span class="text">
        <span class="label">{{ s.label }}</span>
        <span class="hint">{{ s.hint }}</span>
      </span>
    </router-link>
  </nav>
</template>

<style scoped>
.step-nav {
  display: flex;
  gap: 8px;
  padding: 6px;
  margin-bottom: 24px;
  background: #fff;
  border: 1px solid #e8e4e0;
  border-radius: 10px;
  overflow-x: auto;
  scrollbar-width: thin;
}

.step {
  flex: 1 1 0;
  min-width: 150px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  text-decoration: none;
  color: #555;
  transition: background 0.15s, color 0.15s;
}

.step:hover {
  background: #f7f5f2;
}

.step.active {
  background: #eef5f0;
  color: #1a5c38;
}

.step.done .num {
  background: #1a5c38;
  color: #fff;
  border-color: #1a5c38;
}

.num {
  flex: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid #d5d0ca;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #777;
  background: #fff;
}

.step.active .num {
  background: #1a5c38;
  border-color: #1a5c38;
  color: #fff;
}

.text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.label {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
}

.hint {
  font-size: 11px;
  color: #999;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step.active .hint {
  color: #4f7d63;
}

@media (max-width: 720px) {
  .step-nav {
    margin-bottom: 16px;
  }

  .step {
    min-width: 136px;
    padding: 8px 10px;
  }

  .hint {
    display: none;
  }
}
</style>
