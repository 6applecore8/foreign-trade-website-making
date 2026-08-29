<script setup>
defineProps({
  result: { type: Object, required: true },
  startingAgent: { type: Boolean, default: false },
  agentRun: { type: Object, default: null },
  agentError: { type: String, default: "" }
});
defineEmits(["start-agent"]);
</script>

<template>
  <section id="success" class="success">
    <h2>保存成功</h2>
    <dl>
      <dt>request_id</dt><dd id="result-id">{{ result.request_id }}</dd>
      <dt>绝对路径</dt><dd id="result-absolute">{{ result.absolute_path }}</dd>
      <dt>相对路径</dt><dd id="result-relative">{{ result.relative_path }}</dd>
    </dl>
    <div class="agent-launch">
      <div>
        <h3>下一步：让 Agent 开始制作</h3>
        <p>只会启动上方 request_id 对应的不可变需求，页面输入不能指定命令。</p>
      </div>
      <button id="start-agent" type="button" :disabled="startingAgent || Boolean(agentRun)" @click="$emit('start-agent')">
        {{ startingAgent ? "正在通知 Agent…" : agentRun?.status === "completed" ? "网站制作完成" : agentRun?.status === "failed" ? "网站制作失败" : agentRun ? "Agent 正在制作" : "通知 Agent 开始运行" }}
      </button>
    </div>
    <p v-if="agentRun" id="agent-run-status" class="agent-status" :class="agentRun.status === 'failed' ? 'error-text' : 'success-text'" role="status">
      {{ agentRun.status === "completed" ? "制作完成" : agentRun.status === "failed" ? "制作失败" : "执行引擎运行中" }} · {{ agentRun.run_id }}
    </p>
    <p v-if="agentError" id="agent-run-error" class="agent-status error-text" role="alert">{{ agentError }}</p>
  </section>
</template>
