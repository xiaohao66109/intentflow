<script setup lang="ts">
import {computed} from 'vue'

const props=withDefaults(defineProps<{modelValue:string;label?:string;placeholder?:string}>(),{label:'内容',placeholder:'输入一项内容'})
const emit=defineEmits<{(event:'update:modelValue',value:string):void}>()
const items=computed(()=>props.modelValue===''?['']:props.modelValue.split(/\r?\n/))
function update(index:number,value:string){const next=[...items.value];next[index]=value;emit('update:modelValue',next.join('\n'))}
function add(){emit('update:modelValue',[...items.value,''].join('\n'))}
function remove(index:number){emit('update:modelValue',items.value.filter((_,itemIndex)=>itemIndex!==index).join('\n'))}
</script>

<template>
 <div class="text-entries">
  <div v-for="(item,index) in items" :key="index" class="text-entry">
   <el-input :model-value="item" :placeholder="placeholder" :aria-label="`${label} ${index+1}`" @update:model-value="update(index,$event)"/>
   <el-button :aria-label="`删除${label} ${index+1}`" @click="remove(index)">删除</el-button>
  </div>
  <el-button class="add-text-entry" @click="add">添加</el-button>
 </div>
</template>
