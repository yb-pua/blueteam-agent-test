<script setup>
import { useRouter, useRoute } from 'vue-router'
const route = useRoute()
const navItems = [
  { path: '/chat', label: 'AI分析' },
  { path: '/ioc', label: 'IoC查询' },
  { path: '/alert', label: '告警解析' },
  { path: '/daily', label: '情报日报' },
  { path: '/kb', label: '知识库' },
  { path: '/skills', label: '🧩 Skill' },
  { path: '/settings', label: '⚙️ 配置' },
]
</script>

<template>
  <nav style="background: #1e293b; border-bottom: 1px solid #334155;">
    <div class="container" style="display: flex; align-items: center; gap: 32px; height: 56px;">
      <span style="font-weight: 700; color: #60a5fa; font-size: 18px;">蓝队威胁情报平台</span>
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        :style="{ color: route.path === item.path ? '#60a5fa' : '#94a3b8', fontWeight: route.path === item.path ? 600 : 400 }"
      >{{ item.label }}</router-link>
    </div>
  </nav>
  <div class="container">
    <router-view />
  </div>
</template>
