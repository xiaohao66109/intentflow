<script setup lang="ts">
import {computed} from 'vue'
import {naturalEntries,naturalLabel,naturalScalar} from './naturalData'
const props=defineProps<{value:unknown}>()
const isArray=computed(()=>Array.isArray(props.value))
const isObject=computed(()=>!!props.value&&typeof props.value==='object'&&!isArray.value)
const entries=computed(()=>isObject.value?naturalEntries(props.value as Record<string,unknown>):[])
const complex=(value:unknown)=>!!value&&typeof value==='object'
</script>

<template>
 <div class="natural-data">
  <ul v-if="isArray"><li v-for="(item,index) in (value as unknown[])" :key="index"><NaturalData v-if="complex(item)" :value="item"/><span v-else>{{naturalScalar(item)}}</span></li></ul>
  <dl v-else-if="isObject"><template v-for="([key,item]) in entries" :key="key"><dt>{{naturalLabel(key)}}</dt><dd><NaturalData v-if="complex(item)" :value="item"/><span v-else>{{naturalScalar(item)}}</span></dd></template><p v-if="!entries.length">相关记录已保存。</p></dl>
  <p v-else>{{naturalScalar(value)}}</p>
 </div>
</template>
