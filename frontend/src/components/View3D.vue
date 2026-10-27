<script setup lang="ts">
import {
  ref,
  watch,
  onMounted,
  onBeforeUnmount,
  nextTick,
  computed,
} from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { Placement, ContainerKpi } from "@/api";

const props = defineProps<{
  containers: ContainerKpi[];
  placements: Placement[];
}>();

const emit = defineEmits<{
  (e: "select", p: Placement | null): void;
}>();

const canvasEl = ref<HTMLCanvasElement>();
const activeIdx = ref(0);
const selected = ref<Placement | null>(null);
const playing = ref(false);
const playStep = ref(0);
const speed = ref<0.5 | 1 | 2 | 4>(1);
const showAll = ref(false);
const maximized = ref(false);
const fullscreen = ref(false);

let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let containerGroup: THREE.Group | null = null;
let outline: THREE.LineSegments | null = null;
let controls: OrbitControls | null = null;
let animId = 0;
let playTimer: ReturnType<typeof setInterval> | null = null;

const active = computed(
  () => props.containers[activeIdx.value] ?? props.containers[0] ?? null,
);

const containerPlacements = computed(() => {
  if (!active.value) return [];
  const label = active.value.label;
  return props.placements
    .filter((p) => p.container_id !== null && p.label === label)
    .slice()
    .sort((a, b) => (a.load_seq ?? 0) - (b.load_seq ?? 0));
});

const totalSteps = computed(() => containerPlacements.value.length);

function dims(): { l: number; w: number; h: number } {
  const t = active.value;
  if (t && t.payload_capacity_kg > 0) {
    const code = t.type_code || "";
    const map: Record<string, { l: number; w: number; h: number }> = {
      "20GP": { l: 5900, w: 2350, h: 2390 },
      "40GP": { l: 12030, w: 2350, h: 2390 },
      "40HC": { l: 12030, w: 2350, h: 2685 },
      "40HQ": { l: 12030, w: 2350, h: 2685 },
      "45HC": { l: 16150, w: 2350, h: 2685 },
      "20RF": { l: 5900, w: 2350, h: 2390 },
    };
    return map[code] || { l: 5900, w: 2350, h: 2390 };
  }
  return { l: 5900, w: 2350, h: 2390 };
}

function buildScene() {
  if (!canvasEl.value) return;
  const w = canvasEl.value.clientWidth || 800;
  const h = canvasEl.value.clientHeight || 500;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf5f3f0);

  camera = new THREE.PerspectiveCamera(45, w / h, 1, 100000);

  renderer = new THREE.WebGLRenderer({
    canvas: canvasEl.value,
    antialias: true,
  });
  renderer.setSize(w, h);
  renderer.setPixelRatio(window.devicePixelRatio);

  const amb = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(amb);
  const dir = new THREE.DirectionalLight(0xffffff, 0.6);
  dir.position.set(0, 200, 0);
  scene.add(dir);

  containerGroup = new THREE.Group();
  scene.add(containerGroup);

  controls = new OrbitControls(camera, canvasEl.value);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 10;
  controls.maxDistance = 100000;

  canvasEl.value.addEventListener(
    "pointerdown",
    (ev: PointerEvent) => {
      onPointerDown(ev);
    },
  );
  canvasEl.value.addEventListener("pointerup", onPointerUp);
  canvasEl.value.addEventListener("pointerleave", onPointerUp);
  canvasEl.value.addEventListener("wheel", onWheel, { passive: false });
  window.addEventListener("resize", onResize);

  function loop() {
    animId = requestAnimationFrame(loop);
    controls?.update();
    renderer?.render(scene!, camera!);
  }
  loop();
}

function createBox(p: Placement) {
  const dx = p.dim_x;
  const dy = p.dim_y;
  const dz = p.dim_z;
  if (dx <= 0 || dy <= 0 || dz <= 0) return null;

  const mat = new THREE.MeshStandardMaterial({
    color: 0x2f6f4f,
    transparent: true,
    opacity: 0.85,
  });

  // BoxGeometry signature is (width=dx, height=dz, depth=dy); align axes to
  // the container outline so the cargo box and the container frame share the
  // same X/Y/Z orientation. The outline uses (l, h, w) as its dimensions,
  // so map cargo dim_x -> l, dim_z -> h, dim_y -> w.
  const geo = new THREE.BoxGeometry(dx, dz, dy);
  const mesh = new THREE.Mesh(geo, mat);

  // Place the cargo mesh so that dim_x runs along the container's long axis
  // (l), dim_z along the height axis (h), and dim_y along the width axis (w).
  mesh.position.set(
    p.x + dx / 2,
    p.z + dz / 2,
    p.y + dy / 2,
  );

  mesh.userData.importRowId = p.import_row_id;
  mesh.userData.p = p;
  return mesh;
}

function buildContainer3D() {
  if (!scene || !containerGroup || !active.value) return;
  containerGroup.clear();
  clearHighlight();

  const L = dims();

  // The container outline is a box spanning [0,L.l] x [0,L.h] x [0,L.w],
  // matching the cargo placement coordinate system where dim_x (cargo length)
  // runs along the container long axis, dim_z (cargo height) along the
  // vertical axis, and dim_y (cargo width) along the lateral axis.
  const geo = new THREE.BoxGeometry(L.l, L.h, L.w);
  const edges = new THREE.EdgesGeometry(geo);
  const line = new THREE.LineSegments(
    edges,
    new THREE.LineBasicMaterial({ color: 0x888888 }),
  );
  line.position.set(L.l / 2, L.h / 2, L.w / 2);
  containerGroup.add(line);

  const floorGeo = new THREE.PlaneGeometry(L.l, L.w);
  const floor = new THREE.Mesh(
    floorGeo,
    new THREE.MeshBasicMaterial({ color: 0xe8e4e0, side: THREE.DoubleSide }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(L.l / 2, 0, L.w / 2);
  containerGroup.add(floor);

  const shown = showAll.value
    ? containerPlacements.value
    : containerPlacements.value.slice(0, playStep.value + 1);

  for (const p of shown) {
    const mesh = createBox(p);
    if (mesh) containerGroup.add(mesh);
  }
}

function resetView() {
  if (!active.value) return;
  const L = dims();
  const shown = showAll.value
    ? containerPlacements.value
    : containerPlacements.value.slice(0, playStep.value + 1);
  centerOnBounds(shown, L);
}

function centerOnBounds(
  placed: Placement[],
  L: { l: number; w: number; h: number },
) {
  if (!camera || !scene || !controls) return;
  const pts: THREE.Vector3[] = [];
  for (const p of placed) {
    pts.push(new THREE.Vector3(p.x, p.z, p.y));
  }
  if (pts.length === 0) {
    pts.push(new THREE.Vector3(L.l / 2, L.h / 2, L.w / 2));
  }
  const bb = new THREE.Box3();
  for (const p of pts) bb.expandByPoint(p);
  // Expand the box by the container dimensions so the camera always fits the
  // full container outline, not just the placed items.
  bb.expandByPoint(new THREE.Vector3(L.l, L.h, L.w));
  const center = bb.getCenter(new THREE.Vector3());
  const size = bb.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 1000);
  controls.target.copy(center);
  const theta = 0.6;
  const phi = 0.4;
  const radius = maxDim * 1.4;
  camera.position.set(
    center.x + radius * Math.sin(phi) * Math.sin(theta),
    center.y + radius * Math.cos(phi),
    center.z + radius * Math.sin(phi) * Math.cos(theta),
  );
  camera.near = Math.max(radius / 1000, 1);
  camera.updateProjectionMatrix();
  controls.update();
}

function highlight(p: Placement) {
  clearHighlight();
  if (!containerGroup) return;
  for (const obj of containerGroup.children) {
    if (
      obj instanceof THREE.Mesh &&
      obj.userData.importRowId === p.import_row_id
    ) {
      const w = (obj.geometry as THREE.BoxGeometry).parameters.width * 1.02;
      const h = (obj.geometry as THREE.BoxGeometry).parameters.height * 1.02;
      const d = (obj.geometry as THREE.BoxGeometry).parameters.depth * 1.02;
      const geo = new THREE.BoxGeometry(w, h, d);
      const edges = new THREE.EdgesGeometry(geo);
      outline = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: 0xff5500, linewidth: 3 }),
      );
      outline.position.copy(obj.position);
      containerGroup.add(outline);
      (obj.material as THREE.MeshStandardMaterial).color.set(0x1a5c38);
      return;
    }
  }
}

function clearHighlight() {
  if (outline && containerGroup) {
    containerGroup.remove(outline);
    outline.geometry.dispose();
    (outline.material as THREE.Material).dispose();
    outline = null;
  }
}

function rebuild() {
  if (!containerGroup || !scene) return;
  containerGroup.clear();
  clearHighlight();
  buildContainer3D();
}

function onContainerChange(idx: number) {
  activeIdx.value = idx;
  selected.value = null;
  emit("select", null);
  playStep.value = 0;
  stopPlayback();
  rebuild();
}

function startPlayback() {
  stopPlayback();
  playStep.value = 0;
  playing.value = true;
  const ms = 600 / speed.value;
  playTimer = setInterval(() => {
    playStep.value++;
    if (playStep.value >= totalSteps.value) {
      stopPlayback();
      playStep.value = totalSteps.value;
      rebuild();
      return;
    }
    rebuild();
  }, ms);
}

function stopPlayback() {
  if (playTimer) clearInterval(playTimer);
  playTimer = null;
  playing.value = false;
}

function stepForward() {
  stopPlayback();
  playStep.value = Math.min(totalSteps.value, playStep.value + 1);
  rebuild();
}

function stepBack() {
  stopPlayback();
  playStep.value = Math.max(0, playStep.value - 1);
  rebuild();
}

function setSpeed(s: 0.5 | 1 | 2 | 4) {
  speed.value = s;
  if (playing.value) startPlayback();
}

function onPointerDown(ev: PointerEvent) {
  if (!canvasEl.value || !camera) return;
  const startX = ev.clientX;
  const startY = ev.clientY;
  let moved = false;
  const onMove = (mev: PointerEvent) => {
    if (Math.abs(mev.clientX - startX) > 4 || Math.abs(mev.clientY - startY) > 4) moved = true;
  };
  const onUp = () => {
    canvasEl.value?.removeEventListener("pointermove", onMove);
    canvasEl.value?.removeEventListener("pointerup", onUp);
    if (moved) return;
    const rect = canvasEl.value!.getBoundingClientRect();
    const mx = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    const my = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(new THREE.Vector2(mx, my), camera!);
    const meshes = containerGroup?.children.filter(
      (c): c is THREE.Mesh => c instanceof THREE.Mesh,
    );
    const hits = raycaster.intersectObjects(meshes || []);
    if (hits.length > 0) {
      const p = hits[0].object.userData.p;
      if (p) {
        selected.value = p;
        emit("select", p);
        highlight(p);
      }
    } else {
      selected.value = null;
      emit("select", null);
      clearHighlight();
    }
  };
  canvasEl.value.addEventListener("pointermove", onMove);
  canvasEl.value.addEventListener("pointerup", onUp);
}

function onPointerUp() {
  /* no-op */
}

function onWheel(ev: WheelEvent) {
  ev.preventDefault();
}

function onResize() {
  if (!canvasEl.value || !renderer || !camera) return;
  const w = canvasEl.value.clientWidth;
  const h = canvasEl.value.clientHeight;
  if (w === 0 || h === 0) return;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

function toggleFullscreen() {
  fullscreen.value = !fullscreen.value;
  if (fullscreen.value) {
    document.body.style.overflow = "hidden";
  } else {
    document.body.style.overflow = "";
  }
  nextTick(() => onResize());
}

onMounted(async () => {
  await nextTick();
  buildScene();
  resetView();
});

onBeforeUnmount(() => {
  stopPlayback();
  cancelAnimationFrame(animId);
  window.removeEventListener("resize", onResize);
  controls?.dispose();
  renderer?.dispose();
});

watch(
  () => [props.containers, props.placements],
  () => {
    activeIdx.value = 0;
    playStep.value = 0;
    stopPlayback();
    rebuild();
    resetView();
  },
  { deep: false },
);

watch(activeIdx, (v) => onContainerChange(v));

defineExpose({
  startPlayback,
  stopPlayback,
  stepForward,
  stepBack,
  setSpeed,
});
</script>

<template>
  <div class="view3d">
    <div v-if="containers.length > 1" class="tabs">
      <button
        v-for="(c, i) in containers"
        :key="c.label || i"
        :class="['tab', { active: i === activeIdx }]"
        @click="onContainerChange(i)"
      >
        {{ c.label || `箱${i + 1}` }}
      </button>
    </div>

    <div class="canvas-wrap" :class="{ maximized, fullscreen }">
      <canvas ref="canvasEl" class="canvas"></canvas>
      <div v-if="!active" class="empty">暂无集装箱</div>
      <button @click="resetView" class="view-btn" title="复位视角">
        复位视角
      </button>
    </div>

    <div class="controls">
      <button @click="stepBack" :disabled="playStep <= 0" title="上一步">
        &lt;
      </button>
      <button @click="playing ? stopPlayback() : startPlayback()" :class="{ primary: true }">
        {{ playing ? "暂停" : "回放" }}
      </button>
      <button @click="stepForward" :disabled="playStep >= totalSteps - 1" title="下一步">
        &gt;
      </button>
      <span class="step-label">
        步 {{ playStep + 1 }} / {{ totalSteps }}
      </span>

      <label class="speed">
        倍速
        <select v-model="speed" @change="setSpeed(speed as 0.5 | 1 | 2 | 4)">
          <option :value="0.5">0.5×</option>
          <option :value="1">1×</option>
          <option :value="2">2×</option>
          <option :value="4">4×</option>
        </select>
      </label>

      <label class="all-toggle">
        <input type="checkbox" v-model="showAll" @change="rebuild" />
        全部
      </label>
      <button @click="maximized = !maximized" :class="{ 'max-btn': true, active: maximized }" :title="maximized ? '退出最大化' : '最大化'" class="max-btn">
        {{ maximized ? "还原" : "最大化" }}
      </button>
      <button @click="toggleFullscreen" :class="{ 'max-btn': true, active: fullscreen }" :title="fullscreen ? '退出全屏' : '全屏'" class="max-btn">
        {{ fullscreen ? "退出全屏" : "全屏" }}
      </button>
    </div>

    <div v-if="selected" class="sel-info">
      <span class="pn">{{ selected.k_pn }}</span>
      <span>{{ selected.g_packmatls }}</span>
      <span>顺序 {{ selected.load_seq }}</span>
      <span>
        x={{ selected.x }} y={{ selected.y }} z={{ selected.z }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.view3d {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tab {
  padding: 4px 14px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}

.tab.active {
  background: #1a5c38;
  color: #fff;
  border-color: #1a5c38;
}

.canvas-wrap {
  position: relative;
  width: 100%;
  height: clamp(280px, 52vh, 460px);
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  overflow: hidden;
  background: #f5f3f0;
}

.canvas-wrap.maximized {
  height: calc(100vh - 220px);
  min-height: 420px;
}

.canvas-wrap.fullscreen {
  position: fixed;
  inset: 0;
  z-index: 1000;
  height: 100vh;
  width: 100vw;
  margin: 0;
  border-radius: 0;
  background: #111;
}

.view-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  padding: 6px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.9);
  cursor: pointer;
  font-size: 13px;
  color: #333;
}

.max-btn {
  padding: 4px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  color: #555;
}

.max-btn.active {
  background: #1a5c38;
  color: #fff;
  border-color: #1a5c38;
}

.canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
}

.controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.controls button {
  padding: 4px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}

.controls button.primary {
  background: #1a5c38;
  color: #fff;
  border-color: #1a5c38;
}

.controls button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.step-label {
  font-size: 13px;
  color: #555;
}

.speed {
  font-size: 13px;
  color: #555;
  display: flex;
  align-items: center;
  gap: 4px;
}

.speed select {
  padding: 2px 6px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.all-toggle {
  font-size: 13px;
  color: #555;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.sel-info {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 8px 12px;
  background: #f9f7f4;
  border: 1px solid #e8e4e0;
  border-radius: 6px;
  font-size: 13px;
  color: #444;
  flex-wrap: wrap;
}

.sel-info .pn {
  font-weight: 600;
  color: #1a5c38;
}
</style>
