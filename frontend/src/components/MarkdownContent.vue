<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  content: { type: String, default: '' },
})

// 扩展 marked：GFM 表格/任务列表 + 换行
marked.setOptions({
  gfm: true,
  breaks: true,
})

const rendered = computed(() => {
  const raw = props.content || ''
  const html = marked.parse(raw, { async: false })
  return DOMPurify.sanitize(html)
})
</script>

<template>
  <div class="markdown-body" v-html="rendered"></div>
</template>

<style scoped>
.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3) {
  margin: 12px 0 8px;
  color: #f1f5f9;
  line-height: 1.4;
}
.markdown-body :deep(h1) { font-size: 18px; }
.markdown-body :deep(h2) { font-size: 16px; border-bottom: 1px solid #334155; padding-bottom: 4px; }
.markdown-body :deep(h3) { font-size: 14px; }
.markdown-body :deep(p) { margin: 6px 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { margin: 6px 0; padding-left: 22px; }
.markdown-body :deep(li) { margin: 3px 0; }
.markdown-body :deep(strong) { color: #f8fafc; }
.markdown-body :deep(a) { color: #60a5fa; }
.markdown-body :deep(code) {
  background: #0f172a; padding: 2px 6px; border-radius: 4px;
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px; color: #7dd3fc;
}
.markdown-body :deep(pre) {
  background: #0f172a; padding: 12px; border-radius: 6px;
  overflow-x: auto; margin: 8px 0; border: 1px solid #334155;
}
.markdown-body :deep(pre code) { background: transparent; padding: 0; color: #e2e8f0; }
.markdown-body :deep(blockquote) {
  border-left: 3px solid #334155; padding-left: 12px; margin: 8px 0; color: #94a3b8;
}
.markdown-body :deep(table) {
  border-collapse: collapse; margin: 8px 0; width: 100%;
}
.markdown-body :deep(th), .markdown-body :deep(td) {
  border: 1px solid #334155; padding: 6px 10px; font-size: 13px; text-align: left;
}
.markdown-body :deep(th) { background: #1e3a5f; color: #f1f5f9; }
.markdown-body :deep(hr) { border: none; border-top: 1px solid #334155; margin: 10px 0; }
</style>
