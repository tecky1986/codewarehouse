<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import { ALGORITHMS, Jobs, type Job } from "@/api";

const props = defineProps<{
  jobId: number;
  taskName?: string;
}>();

const emit = defineEmits<{
  (e: "done", job: Job): void;
  (e: "failed", job: Job): void;
}>();

const job = ref<Job | null>(null);
const nowTick = ref(Date.now());
let poll: ReturnType<typeof setInterval> | null = null;
let clock: ReturnType<typeof setInterval> | null = null;

const statusText = computed(() => {
  const s = job.value?.status;
  if (s === "running") return "计算中";
  if (s === "done") return "已完成";
  if (s === "failed") return "失败";
  return s || "";
});

const ALGO_LABEL: Record<string, string> = Object.fromEntries(
  ALGORITHMS.map((a) => [a.key, a.label]),
);

function algoName(raw: unknown): string {
  if (typeof raw === "string") return raw;
  if (raw && typeof raw === "object" && "name" in (raw as object)) {
    return String((raw as { name: string }).name);
  }
  return String(raw ?? "");
}

const algoList = computed(() => {
  const list = job.value?.algorithms || [];
  return list.map((a) => algoName(a)).filter(Boolean);
});

const overallPct = computed(() => {
  const names = algoList.value;
  if (!names.length) return 0;
  const sum = names.reduce((s, n) => s + pctOf(n), 0);
  return Math.round(sum / names.length);
});

const elapsedLabel = computed(() => {
  const j = job.value;
  if (!j) return "0s";
  const sec =
    j.elapsed_s != null
      ? j.elapsed_s
      : j.started_at
        ? Math.max(0, nowTick.value / 1000 - Number(j.started_at))
        : 0;
  if (sec < 60) return `${Math.floor(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}分${s.toString().padStart(2, "0")}秒`;
});

onMounted(async () => {
  clock = setInterval(() => {
    nowTick.value = Date.now();
  }, 500);
  try {
    const j = await Jobs.get(props.jobId);
    job.value = j;
    if (j.status === "running") {
      poll = setInterval(async () => {
        try {
          const jj = await Jobs.get(props.jobId);
          job.value = jj;
          if (jj.status !== "running") {
            stop();
            if (jj.status === "done") emit("done", jj);
            else emit("failed", jj);
          }
        } catch {
          /* keep last snapshot */
        }
      }, 400);
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
  if (clock) clearInterval(clock);
  clock = null;
}

function algoRow(name: string) {
  const list = job.value?.algorithms || [];
  const found = list.find((a) => typeof a !== "string" && a.name === name) as
    | {
        name: string;
        progress?: number;
        eta_seconds?: number;
        timed_out?: boolean;
        done_ms?: number;
      }
    | undefined;
  const progress =
    found?.progress != null
      ? found.progress
      : job.value?.progress?.[name] != null
        ? job.value!.progress![name]
        : 0;
  const eta = found?.eta_seconds != null ? found.eta_seconds : job.value?.eta_seconds?.[name];
  return { progress, eta, timed_out: found?.timed_out, done_ms: found?.done_ms };
}

function pctOf(name: string) {
  const p = algoRow(name).progress;
  if (p == null) return 0;
  return Math.round(p * 100);
}

function etaLabel(name: string) {
  const r = algoRow(name);
  if (r.timed_out) return "超时截断";
  if (r.progress >= 1 || r.done_ms != null) return "完成";
  if (r.eta != null && r.eta > 0) return `剩余约 ${Math.round(r.eta)}s`;
  if (r.progress > 0) return "计算中";
  return "排队中";
}
</script>

<template>
  <div class="job-progress" v-if="job">
    <div class="header">
      <span class="status" :class="job.status">{{ statusText }}</span>
      <span v-if="taskName" class="task">{{ taskName }}</span>
      <span class="elapsed">已用 {{ elapsedLabel }}</span>
      <span class="overall">{{ overallPct }}%</span>
    </div>

    <div class="overall-track">
      <div class="overall-fill" :style="{ width: overallPct + '%' }"></div>
    </div>

    <div class="rows">
      <div v-for="name in algoList" :key="name" class="row">
        <span class="name">{{ ALGO_LABEL[name] || name }}</span>
        <div class="bar-wrap">
          <div
            class="bar"
            :class="{ done: pctOf(name) >= 100, pulse: pctOf(name) > 0 && pctOf(name) < 100 }"
            :style="{ width: pctOf(name) + '%' }"
          ></div>
        </div>
        <span class="pct">{{ pctOf(name) }}%</span>
        <span class="eta">{{ etaLabel(name) }}</span>
      </div>
    </div>

    <p v-if="job.status === 'running'" class="hint">
      各算法并行计算，进度按已装箱件数更新；长时间无变化通常是在搜索空位。
    </p>
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
  margin-bottom: 10px;
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

.elapsed {
  margin-left: auto;
  font-size: 12px;
  color: #777;
}

.overall {
  font-size: 16px;
  font-weight: 600;
  color: #1a5c38;
  min-width: 48px;
  text-align: right;
}

.overall-track {
  height: 8px;
  background: #e8e4e0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 14px;
}

.overall-fill {
  height: 100%;
  background: #1a5c38;
  transition: width 0.3s;
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
  width: 88px;
  font-size: 13px;
  color: #333;
  font-weight: 500;
}

.bar-wrap {
  flex: 1;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.bar {
  height: 100%;
  background: #1a5c38;
  transition: width 0.3s;
}

.bar.pulse {
  background: linear-gradient(90deg, #1a5c38 0%, #3d8b5e 50%, #1a5c38 100%);
  background-size: 200% 100%;
  animation: sweep 1.4s linear infinite;
}

.bar.done {
  background: #1a5c38;
  animation: none;
}

@keyframes sweep {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

.pct {
  font-size: 12px;
  color: #1a5c38;
  min-width: 36px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.eta {
  font-size: 12px;
  color: #777;
  min-width: 88px;
  text-align: right;
}

.hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: #888;
}

.error {
  margin-top: 10px;
  font-size: 13px;
  color: #c62828;
}
</style>
