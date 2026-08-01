import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/chat' },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../views/ChatView.vue'),
    meta: { title: 'AI 威胁分析' }
  },
  {
    path: '/ioc',
    name: 'ioc',
    component: () => import('../views/IoCQuery.vue'),
    meta: { title: 'IoC查询' }
  },
  {
    path: '/alert',
    name: 'alert',
    component: () => import('../views/AlertParser.vue'),
    meta: { title: '告警解析' }
  },
  {
    path: '/daily',
    name: 'daily',
    component: () => import('../views/DailyBrief.vue'),
    meta: { title: '情报日报' }
  },
  {
    path: '/kb',
    name: 'kb',
    component: () => import('../views/KnowledgeBase.vue'),
    meta: { title: '知识库' }
  },
  {
    path: '/skills',
    name: 'skills',
    component: () => import('../views/SkillsView.vue'),
    meta: { title: 'Skill' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../views/SettingsView.vue'),
    meta: { title: '配置' }
  },
]

export default createRouter({ history: createWebHistory(), routes })
