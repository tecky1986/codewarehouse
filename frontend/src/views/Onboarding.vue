<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const steps = [
  {
    title: "1. 创建任务",
    desc: "在任务页新建一个装箱任务，命名清晰便于后续查找。",
    action: () => router.push("/tasks"),
    label: "去任务页",
  },
  {
    title: "2. 导入样表",
    desc: "上传 Excel 文件，系统自动识别列、补齐缺失规格并检查可计算状态。",
    action: () => router.push("/tasks"),
    label: "查看任务",
  },
  {
    title: "3. 配置参数",
    desc: "在全局参数中设定人工搬运上限、叉车铲齿、算法时限和货物间隙。",
    action: () => router.push("/settings"),
    label: "打开参数",
  },
  {
    title: "4. 规则与箱型",
    desc: "在任务详情里完成 Site 确认、规则配置和箱型选择，再开始计算。",
    action: () => router.push("/tasks"),
    label: "打开任务列表",
  },
  {
    title: "5. 对比与导出",
    desc: "查看 KPI 对照、采用最佳方案，并导出 xlsx / csv 报表。",
    action: () => router.push("/tasks"),
    label: "开始使用",
  },
];

const currentIndex = computed(() => 0);
</script>

<template>
  <div class="page">
    <div class="hero">
      <p class="eyebrow">首次使用引导</p>
      <h1>欢迎使用集装箱装箱工具</h1>
      <p class="intro">
        按以下步骤即可完成任务创建、样表导入、参数设置和方案计算。
      </p>
      <button class="primary" @click="router.push('/tasks')">开始使用</button>
    </div>

    <div class="steps">
      <div v-for="(step, index) in steps" :key="step.title" class="step-card">
        <div class="badge">{{ index + 1 }}</div>
        <div class="content">
          <h2>{{ step.title }}</h2>
          <p>{{ step.desc }}</p>
          <button class="ghost" @click="step.action()">{{ step.label }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  max-width: 980px;
  margin: 0 auto;
  padding: 32px 40px 56px;
}

.hero {
  background: linear-gradient(135deg, #f3f7f4, #ffffff);
  border: 1px solid #e8e4e0;
  border-radius: 12px;
  padding: 28px 28px 24px;
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  color: #1a5c38;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

h1 {
  margin: 0;
  font-size: 28px;
  color: #2c2c2c;
}

.intro {
  margin: 12px 0 20px;
  font-size: 15px;
  color: #666;
  line-height: 1.6;
}

.primary,
.ghost {
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
}

.primary {
  background: #1a5c38;
  color: #fff;
}

.ghost {
  background: #f5f3f0;
  color: #2c2c2c;
  border: 1px solid #e8e4e0;
}

.steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.step-card {
  background: #fff;
  border: 1px solid #e8e4e0;
  border-radius: 10px;
  display: flex;
  gap: 14px;
  padding: 18px 16px;
}

.badge {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #eaf3ee;
  color: #1a5c38;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.content {
  flex: 1;
}

.content h2 {
  margin: 0 0 8px;
  font-size: 16px;
  color: #2c2c2c;
}

.content p {
  margin: 0 0 12px;
  font-size: 13px;
  color: #666;
  line-height: 1.6;
}
</style>
