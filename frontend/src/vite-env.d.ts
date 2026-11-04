/// <reference types="vite/client" />

declare const __RELEASE_META__: {
  version: string;
  date: string;
};

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}
