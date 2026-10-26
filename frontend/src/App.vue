<template>
  <div class="app-shell">
    <header class="header">
      <router-link to="/onboarding" class="brand">集装箱装箱工具</router-link>
      <nav class="nav">
        <router-link to="/onboarding">引导</router-link>
        <router-link to="/tasks">任务</router-link>
        <router-link to="/container-types">箱型</router-link>
        <router-link to="/packages">主数据</router-link>
        <router-link to="/export-templates">导出</router-link>
        <router-link to="/settings">参数</router-link>
      </nav>
    </header>
    <router-view />
  </div>
</template>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, "Segoe UI", "Noto Sans SC", sans-serif;
  background: #f5f3f0;
  color: #2c2c2c;
}

.app-shell {
  min-height: 100vh;
}

.header {
  background: #fff;
  border-bottom: 1px solid #e8e4e0;
  padding: 12px 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 10;
}

.brand {
  font-size: 15px;
  font-weight: 600;
  color: #1a5c38;
  text-decoration: none;
}

.nav {
  display: flex;
  gap: 20px;
}

.nav a {
  font-size: 14px;
  color: #555;
  text-decoration: none;
  padding: 4px 0;
}

.nav a:hover,
.nav a.router-link-exact-active {
  color: #1a5c38;
}
</style>
