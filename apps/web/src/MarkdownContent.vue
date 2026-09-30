<script setup lang="ts">
import {computed} from 'vue'
import {parseMarkdown,type MarkdownInline} from './markdown'
const props=defineProps<{source:string}>()
const blocks=computed(()=>parseMarkdown(props.source))
const heading=(level?:number)=>`h${Math.min(6,Math.max(1,level||2))}`
const parts=(line?:MarkdownInline[])=>line||[]
</script>

<template>
 <div class="markdown-content">
  <template v-for="(block,index) in blocks" :key="index">
   <component :is="heading(block.level)" v-if="block.kind==='heading'"><template v-for="(part,i) in parts(block.lines?.[0])" :key="i"><strong v-if="part.kind==='strong'">{{part.text}}</strong><code v-else-if="part.kind==='code'">{{part.text}}</code><template v-else>{{part.text}}</template></template></component>
   <p v-else-if="block.kind==='paragraph'||block.kind==='quote'" :class="{quote:block.kind==='quote'}"><template v-for="(part,i) in parts(block.lines?.[0])" :key="i"><strong v-if="part.kind==='strong'">{{part.text}}</strong><code v-else-if="part.kind==='code'">{{part.text}}</code><template v-else>{{part.text}}</template></template></p>
   <component :is="block.kind==='ordered'?'ol':'ul'" v-else-if="block.kind==='ordered'||block.kind==='unordered'"><li v-for="(line,i) in block.lines" :key="i"><template v-for="(part,j) in line" :key="j"><strong v-if="part.kind==='strong'">{{part.text}}</strong><code v-else-if="part.kind==='code'">{{part.text}}</code><template v-else>{{part.text}}</template></template></li></component>
   <pre v-else-if="block.kind==='code'"><code>{{block.text}}</code></pre>
   <hr v-else-if="block.kind==='rule'"/>
  </template>
 </div>
</template>
