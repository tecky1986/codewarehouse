<script setup lang="ts">
/**
 * 校验码提示组件。
 *
 * 把一段包含 E 校验码的文本（如 "E102×3 E109" 或 "通过"）渲染为带悬停
 * 提示的标签：鼠标悬停在任一校验码上时，浮层显示该码的具体含义。
 * 文本中没有已知校验码时原样输出。
 */

import { computed } from "vue";
import { VERIFY_CODES } from "@/utils/verifyCodes";

const VERDICTS = new Set(["通过", "未通过", "—"]);

const CODES_RE = /E(\d{3})(×(\d+))?/g;

const props = defineProps<{
  text: string;
}>();

/** 把 "E102×3 E109" 拆分为 [ {code:"E102", count:3}, {code:"E109", count:1} ] */
const entries = computed(() => {
  if (!props.text || VERDICTS.has(props.text)) return [];
  const out: { code: string; count: number }[] = [];
  const seen = new Set<string>();
  for (const m of props.text.matchAll(CODES_RE)) {
    const num = m[1];
    const key = num + (m[3] || "1");
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ code: "E" + num, count: m[3] ? Number(m[3]) : 1 });
  }
  return out;
});

function meaning(code: string): string {
  return VERIFY_CODES[code] ?? "未知校验码";
}
</script>

<template>
  <span v-if="entries.length" class="vc">
    <template v-for="e in entries" :key="e.code + e.count">
      <span class="chip" :title="meaning(e.code) + (e.count > 1 ? `（出现 ${e.count} 次）` : '')">
        <span class="chip-code">{{ e.code }}</span>
        <span v-if="e.count > 1" class="chip-count">×{{ e.count }}</span>
      </span>
    </template>
    <span class="vc-legend">悬停查看校验码含义</span>
  </span>
  <span v-else class="vc-plain">{{ text }}</span>
</template>
<style scoped>
.vc {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.vc-legend {
  font-size: 11px;
  color: #b0a89e;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px 7px;
  border-radius: 10px;
  background: #fbeaea;
  border: 1px solid #f0c9c9;
  cursor: help;
  line-height: 1.5;
}

.chip:hover {
  background: #f7dada;
  border-color: #d98c8c;
}

.chip-code {
  font-family: ui-monospace, monospace;
  font-size: 12px;
  font-weight: 600;
  color: #c62828;
}

.chip-count {
  font-size: 11px;
  color: #8a4a4a;
}

.vc-plain {
  font-size: inherit;
}
</style>
