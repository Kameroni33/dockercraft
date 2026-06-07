import { createRouter, createWebHashHistory } from "vue-router";
import DashboardView from "./views/DashboardView.vue";

// Hash history: the manager serves the UI as plain static files — no
// server-side fallback routing needed for deep links.
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", name: "dashboard", component: DashboardView },
    { path: "/new", name: "setup", component: () => import("./views/SetupWizardView.vue") },
    {
      path: "/server/:id",
      name: "server",
      component: () => import("./views/ServerDetailView.vue"),
      props: (route) => ({ id: Number(route.params.id) }),
    },
    { path: "/backups", name: "backups", component: () => import("./views/BackupsView.vue") },
  ],
});
