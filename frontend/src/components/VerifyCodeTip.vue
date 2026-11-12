<script setup lang="ts">
/**
 * 校验码提示组件。
 *
 * 把一段包含 E 校验码的文本（如 "E102×3 E109" 或 "通过"）渲染为带悬停
 * 提示的标签：鼠标悬停在任一校验码上时，浮层显示该码的具体含义。
 * 文本中没有已知校验码时原样输出。
 */

import { computed } from "vue";

const VERDICTS = new Set(["通过", "未通过", "—"]);

const CODE_MEANINGS: Record<string, string> = {
  E101: "外侧货物阻挡内侧货物——外层箱遮蔽了内层箱的取货路径。",
  E102: "当前排尚未完成——新的一排在前一排未填满时即被开启；砌墙/切割算法遵守行纪律，DBLF/最大空腔/极点算法可能出现此码。",
  E103: "上层货物缺少支撑——悬空货物下方无承托。",
  E104: "叉车进入路径被阻挡——叉车从门口向内侧前进时，同 y 带内已有货物高出叉车工作高度，挡住了货叉。",
  E105: "货物放置路径发生碰撞——放置过程中货叉与已有货物碰撞。",
  E106: "货叉无法退出——卸货时货叉被相邻货物卡住，无法水平退出。",
  E107: "叉车无法倒退出柜——卸货完成后叉车无法从柜内倒退出门。",
  E108: "门架举升高度不足——货物顶部超过门架/门框高度，叉车无法举升到位。",
  E109: "货物无法通过柜门——货物尺寸超过柜门开口（门宽/门高）。",
  E110: "货物超过下层承重——被压货物的每箱承重量（max_load）超限；max_load=0 表示不可被压。",
  E111: "装载顺序存在循环依赖——A 压在 B 上，B 又压在 A 上，形成无法打破的循环。",
  E112: "未预留叉车作业空间——货物布置导致叉车无法在柜内正常作业。",
};

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
  return CODE_MEANINGS[code] ?? "未知校验码";
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
