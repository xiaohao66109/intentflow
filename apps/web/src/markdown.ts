export type MarkdownInline={kind:'text'|'strong'|'code';text:string}
export type MarkdownBlock={kind:'heading'|'paragraph'|'unordered'|'ordered'|'quote'|'code'|'rule';level?:number;lines?:MarkdownInline[][];text?:string}

export function parseInline(source:string):MarkdownInline[]{
 const result:MarkdownInline[]=[]
 const pattern=/(\*\*[^*]+\*\*|`[^`]+`)/g
 let start=0
 for(const match of source.matchAll(pattern)){
  if((match.index||0)>start)result.push({kind:'text',text:source.slice(start,match.index)})
  const token=match[0]
  result.push({kind:token.startsWith('**')?'strong':'code',text:token.startsWith('**')?token.slice(2,-2):token.slice(1,-1)})
  start=(match.index||0)+token.length
 }
 if(start<source.length)result.push({kind:'text',text:source.slice(start)})
 return result.length?result:[{kind:'text',text:''}]
}

export function parseMarkdown(source:string):MarkdownBlock[]{
 const blocks:MarkdownBlock[]=[]
 const raw=String(source||'').replace(/^\uFEFF/,'')
 const normalized=!raw.includes('\n')&&raw.includes('\\n')?raw.replace(/\\r\\n|\\n|\\r/g,'\n'):raw
 const lines=normalized.replace(/\r\n?/g,'\n').split('\n')
 let paragraph:string[]=[]
 const flushParagraph=()=>{if(paragraph.length){blocks.push({kind:'paragraph',lines:[parseInline(paragraph.join(' '))]});paragraph=[]}}
 for(let index=0;index<lines.length;){
  const line=lines[index]
  if(/^```/.test(line)){
   flushParagraph();const language=line.slice(3).trim();const code:string[]=[];index++
   while(index<lines.length&&!/^```/.test(lines[index]))code.push(lines[index++])
   if(index<lines.length)index++
   blocks.push({kind:'code',text:code.join('\n'),lines:language?[[{kind:'text',text:language}]]:undefined});continue
  }
  const heading=line.match(/^\s{0,3}(#{1,6})\s*(\S.*?)(?:\s+#+)?\s*$/)
  if(heading){flushParagraph();blocks.push({kind:'heading',level:heading[1].length,lines:[parseInline(heading[2])]});index++;continue}
  if(/^\s*[-*_]{3,}\s*$/.test(line)){flushParagraph();blocks.push({kind:'rule'});index++;continue}
  if(/^>\s?/.test(line)){flushParagraph();const quote:string[]=[];while(index<lines.length&&/^>\s?/.test(lines[index]))quote.push(lines[index++].replace(/^>\s?/,''));blocks.push({kind:'quote',lines:[parseInline(quote.join(' '))]});continue}
  const list=line.match(/^\s*([-*+] |\d+[.)] )(.+)$/)
  if(list){flushParagraph();const ordered=/^\d/.test(list[1]);const items:MarkdownInline[][]=[];while(index<lines.length){const item=lines[index].match(/^\s*([-*+] |\d+[.)] )(.+)$/);if(!item||/^\d/.test(item[1])!==ordered)break;items.push(parseInline(item[2]));index++}blocks.push({kind:ordered?'ordered':'unordered',lines:items});continue}
  if(!line.trim()){flushParagraph();index++;continue}
  paragraph.push(line.trim());index++
 }
 flushParagraph();return blocks
}
