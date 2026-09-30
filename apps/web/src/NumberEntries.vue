<script setup lang="ts">
import {ref,watch} from 'vue'
const props=defineProps<{modelValue:string;label:string;nameLabel?:string;integer?:boolean}>()
const emit=defineEmits<{(e:'update:modelValue',value:string):void}>()
const rows=ref<{name:string;value:string}[]>([])
const error=ref('')
let emitted=''
watch(()=>props.modelValue,value=>{if(value===emitted)return;try{rows.value=Object.entries(JSON.parse(value||'{}')).map(([name,v])=>({name,value:String(v)}));error.value=''}catch{error.value='原有数据无法读取，请核对后重新填写。'}},{immediate:true})
function update(){
 const active=rows.value.filter(r=>r.name.trim()||r.value!=='')
 const names=active.map(r=>r.name.trim())
 if(active.some(r=>!r.name.trim()||r.value===''||!Number.isFinite(Number(r.value))||(props.integer&&(!Number.isInteger(Number(r.value))||Number(r.value)<0)))||new Set(names).size!==names.length){error.value='请填写不重复的名称和有效数值。';emitted='';emit('update:modelValue','');return}
 error.value='';emitted=JSON.stringify(Object.fromEntries(active.map(r=>[r.name.trim(),Number(r.value)])));emit('update:modelValue',emitted)
}
function remove(index:number){rows.value.splice(index,1);update()}
</script>
<template><fieldset class="number-entries"><legend>{{label}}</legend><p v-if="!rows.length">{{integer?'未设置分组限制。':'尚未填写指标，可留空。'}}</p><div v-for="(row,index) in rows" :key="index" class="number-entry"><label>{{nameLabel||'指标名称'}}<input v-model="row.name" :aria-label="(nameLabel||'指标名称')+' '+(index+1)" :placeholder="integer?'例如：普通':'例如：实际人数'" @input="update"/></label><label>数值<input v-model="row.value" type="number" :step="integer?1:'any'" :min="integer?0:undefined" :aria-label="'数值 '+(index+1)" @input="update"/></label><button type="button" @click="remove(index)">移除</button></div><p v-if="error" role="alert">{{error}}</p><button type="button" @click="rows.push({name:'',value:''})">{{integer?'添加分组配额':'添加指标'}}</button></fieldset></template>
