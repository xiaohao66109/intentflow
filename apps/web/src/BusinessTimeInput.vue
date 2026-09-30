<script setup lang="ts">
import {computed} from 'vue'
const props=defineProps<{modelValue:number;label:string}>()
const emit=defineEmits<{(e:'update:modelValue',value:number):void}>()
const day=computed(()=>Math.floor(props.modelValue/1440))
const time=computed(()=>`${String(Math.floor(props.modelValue%1440/60)).padStart(2,'0')}:${String(props.modelValue%60).padStart(2,'0')}`)
function changeTime(event:Event){const value=(event.target as HTMLInputElement).value;if(!/^\d{2}:\d{2}$/.test(value))return;const [h,m]=value.split(':').map(Number);emit('update:modelValue',day.value*1440+h*60+m)}
function changeDay(event:Event){const value=Number((event.target as HTMLInputElement).value);if(Number.isInteger(value)&&value>=1)emit('update:modelValue',(value-1)*1440+props.modelValue%1440)}
</script>
<template><div class="business-time"><label>{{label}}<input type="time" :aria-label="label" :value="time" required @input="changeTime"/></label><label class="time-day">日期<select v-if="day<2" :aria-label="label+'日期'" :value="day+1" @change="changeDay"><option :value="1">当日</option><option :value="2">次日</option></select><input v-else type="number" min="1" :aria-label="label+'第几天'" :value="day+1" @change="changeDay"/></label></div></template>
