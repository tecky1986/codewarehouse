// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import JobProgress from "@/components/JobProgress.vue";

// JobProgress polling / UI rendering
describe("JobProgress", () => {
  it("renders running state with progress bars", () => {
    const job = {
      id: 1,
      status: "running",
      algorithms: [
        { name: "dblf", progress: 0.5, eta_seconds: 12 },
        { name: "lfh", progress: 0, eta_seconds: 0 },
      ],
    };
    // Mock fetch to return a running job
    globalThis.fetch = (async () => ({
      json: async () => ({ code: 0, message: "", data: job }),
      status: 200,
    })) as unknown as typeof fetch;

    const wrapper = mount(JobProgress, {
      props: { jobId: 1 },
    });
    // Wait a tick for onMounted fetch
    return new Promise((resolve) => setTimeout(resolve, 50)).then(() => {
      expect(wrapper.find(".status.running").exists()).toBe(true);
      expect(wrapper.findAll(".row").length).toBe(2);
      expect(wrapper.text()).toContain("dblf");
      expect(wrapper.text()).toContain("lfh");
      wrapper.unmount();
    });
  });
});
