<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import { Jobs, type Job } from "@/api";

const props = defineProps<{
  jobId: number;
  taskName?: string;
}>();

const emit = defineEmits<{
  (e: "done", job: Job): void;
  (e: "failed", job: Job): void;
}>();

const job = ref<Job | null>(null);
let poll: ReturnType<typeof setInterval> | null = null;

const finished = computed(() =>
  job.value?.status === "done" || job.value?.status === "failed",
);

onMounted(async () => {
  try {
    const j = await Jobs.get(props.jobId);
    job.value = j;
    if (j.status === "running") {
      poll = setInterval(async () => {
        const jj = await Jobs.get(props.jobId);
        job.value = jj;
        if (jj.status !== "running") {
          stop();
          if (jj.status === "done") emit("done", jj);
          else emit("failed", jj);
        }
      }, 1000);
    } else {
      if (j.status === "done") emit("done", j);
      else emit("failed", j);
    }
  } catch {
    /* ignore */
  }
});

onBeforeUnmount(stop);

function stop() {
  if (poll) clearInterval(poll);
  poll = null;
}

function algoRow(a: {
  name: string;
  progress?: number;
  eta_seconds?: number;
  done_ms?: number;
  timed_out?: boolean;
}) {
  const progress =
    a.progress != null
      ? a.progress
      : job.value?.progress?.[a.name] != null
        ? job.value!.progress![a.name]
        : 0;
  const eta =
    a.eta_seconds != null
      ? a.eta_seconds
      : job.value?.eta_seconds?.[a.name];
  return { progress, eta };
}

function pct(progress?: number) {
  if (progress == null) return 0;
  return Math.round(progress * 100);
}

function etaLabel(a: { name: string; progress?: number; eta_seconds?: number; done_ms?: number; timed_out?: boolean }) {
  const r = algoRow(a);
  if (r.progress >= 1 && !a.timed_out) return "完成";
  if (a.done_ms != null) return "完成";
  if (a.timed_out) return "超时";
  if (r.eta != null && r.eta > 0) return `约 ${Math.round(r.eta)}s`;
  if (r.progress >= 1) return "即将完成";
  return "…";
}
</script>

<template>
  <div class="job-progress" v-if="job">
    <div class="header">
      <span class="status" :class="job.status">{{ job.status }}</span>
      <span v-if="taskName" class="task">{{ taskName }}</span>
      <span v-if="finished && job.status === 'failed'" class="task">计算失败</span>
    </div>

    <div class="rows">
      <div v-for="a in job.algorithms" :key="a.name" class="row">
        <span class="name">{{ a.name }}</span>
        <div class="bar-wrap">
          <div class="bar" :style="{ width: pct(algoRow(a).progress) + '%' }"></div>
        </div>
        <span class="eta">{{ etaLabel(a) }}</span>
        <span v-if="a.timed_out" class="timeout">超时</span>
      </div>
    </div>

    <div v-if="job.error" class="error">{{ job.error }}</div>
  </div>
</template>

<style scoped>
.job-progress {
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 16px;
  background: #faf8f6;
}

.header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.status {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 3px;
  background: #e8f5e9;
  color: #1a5c38;
}

.status.running {
  background: #fff8e1;
  color: #8d6e00;
}

.status.done {
  background: #e8f5e9;
  color: #1a5c38;
}

.status.failed {
  background: #fde8e8;
  color: #c62828;
}

.task {
  font-size: 13px;
  color: #555;
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.name {
  width: 110px;
  font-size: 13px;
  color: #333;
  font-weight: 500;
}

.bar-wrap {
  flex: 1;
  height: 6px;
  background: #e0e0e0;
  border-radius: 3px;
  overflow: hidden;
}

.bar {
  height: 100%;
  background: #1a5c38;
  transition: width 0.3s;
}

.eta {
  font-size: 12px;
  color: #777;
  min-width: 60px;
  text-align: right;
}

.timeout {
  font-size: 11px;
  color: #c62828;
}

.error {
  margin-top: 10px;
  font-size: 13px;
  color: #c62828;
}
</style>
