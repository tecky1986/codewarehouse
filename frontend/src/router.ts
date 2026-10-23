import { createRouter, createWebHistory } from "vue-router";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/tasks" },
    { path: "/tasks", component: () => import("@/views/TaskList.vue") },
    {
      path: "/tasks/:id",
      component: () => import("@/views/TaskDetail.vue"),
      props: true,
    },
    {
      path: "/tasks/:id/import",
      component: () => import("@/views/ImportPreview.vue"),
      props: true,
    },
    {
      path: "/tasks/:id/site",
      component: () => import("@/views/SiteConfirm.vue"),
      props: true,
    },
    {
      path: "/tasks/:id/rules",
      component: () => import("@/views/RulesConfig.vue"),
      props: true,
    },
    {
      path: "/tasks/:id/kpi",
      component: () => import("@/views/KpiCompare.vue"),
      props: true,
    },
    {
      path: "/tasks/:id/view3d",
      component: () => import("@/views/View3DPage.vue"),
      props: true,
    },
    {
      path: "/container-types",
      component: () => import("@/views/ContainerTypes.vue"),
    },
    { path: "/packages", component: () => import("@/views/Packages.vue") },
    {
      path: "/export-templates",
      component: () => import("@/views/ExportTemplates.vue"),
    },
    { path: "/settings", component: () => import("@/views/GlobalSettings.vue") },
  ],
});

export default router;
