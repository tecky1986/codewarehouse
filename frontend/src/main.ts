import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";

document.title = `集装箱装箱工具 ${__RELEASE_META__.version}（${__RELEASE_META__.date}）`;
createApp(App).use(router).mount("#app");
