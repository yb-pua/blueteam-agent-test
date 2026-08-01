<script setup>
import { ref, onMounted } from 'vue'
import { apiGet } from '../api/client.js'

const techniques = ref([])
const selectedTech = ref(null)

onMounted(async () => {
  try {
    const data = await apiGet('/kb/techniques')
    techniques.value = data.techniques || data
  } catch (e) {
    techniques.value = []
  }
})

async function selectTech(id) {
  try {
    const data = await apiGet(`/kb/techniques/${id}`)
    selectedTech.value = data
  } catch (e) {
    selectedTech.value = null
  }
}
</script>

<template>
  <div class="card" style="margin-top: 20px;">
    <h2>攻击手法知识库</h2>
    <div style="display: grid; grid-template-columns: 280px 1fr; gap: 16px;">
      <div>
        <div v-for="t in techniques" :key="t.id"
          @click="selectTech(t.id)"
          style="padding: 10px; margin-bottom: 4px; border-radius: 6px; cursor: pointer; background: #0f172a;"
          :style="selectedTech && selectedTech.id === t.id ? { borderLeft: '3px solid #2563eb' } : {}">
          <strong style="font-size: 14px;">{{ t.id }}</strong>
          <div style="font-size: 13px; color: #94a3b8;">{{ t.name }}</div>
          <span class="tag" v-for="tac in (t.tactics || [t.tactic])" :key="tac">{{ tac }}</span>
        </div>
      </div>
      <div v-if="selectedTech">
        <h3>{{ selectedTech.id }}: {{ selectedTech.name }}</h3>
        <span class="tag" v-for="tac in (selectedTech.tactics || [selectedTech.tactic])" :key="tac">{{ tac }}</span>
        <p class="mt-4" style="line-height: 1.6;">{{ selectedTech.description }}</p>
        <div class="mt-4">
          <strong>检测方法：</strong>
          <ul style="margin-top: 8px; padding-left: 20px; color: #94a3b8;">
            <li v-for="d in (Array.isArray(selectedTech.detection) ? selectedTech.detection : [selectedTech.detection])" :key="d">{{ d }}</li>
          </ul>
        </div>
        <div class="highlight-box mt-4"><strong>加固建议：</strong>{{ selectedTech.mitigation }}</div>
      </div>
      <div v-else style="color: #94a3b8; display: flex; align-items: center; justify-content: center; min-height: 200px;">
        选择一个攻击手法查看详情
      </div>
    </div>
  </div>
</template>
