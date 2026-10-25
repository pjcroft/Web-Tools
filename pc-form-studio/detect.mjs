export function findBlankBoxes(canvas,scale=1){
 const {width:w,height:h}=canvas,ctx=canvas.getContext('2d',{willReadFrequently:true}),d=ctx.getImageData(0,0,w,h).data;
 const dark=(x,y)=>{if(x<0||y<0||x>=w||y>=h)return false;let z=(y*w+x)*4;return d[z]<248&&d[z+1]<248&&d[z+2]<248;};
 const horizontal=(x,y,len)=>{let n=0;for(let i=0;i<len;i++)if(dark(x+i,y)||dark(x+i,y-1)||dark(x+i,y+1))n++;return n/len>.91;};
 const vertical=(x,y,len)=>{let n=0;for(let i=0;i<len;i++)if(dark(x,y+i)||dark(x-1,y+i)||dark(x+1,y+i))n++;return n/len>.90;};
 let boxes=[];
 for(let y=20;y<h-10;y++)for(let x=20;x<w-8;x++){
  if(!dark(x,y)||dark(x-1,y))continue;
  let e=x;while(e<w&&dark(e,y))e++;
  const len=e-x;if(len<7*scale||len>w-30){x=e;continue;}
  // A horizontal table rule can contain multiple cells; find every vertical junction.
  let joints=[];for(let xx=x;xx<e;xx++)if(dark(xx,y+3)&&dark(xx,y+5)&&(!joints.length||xx-joints[joints.length-1]>3*scale))joints.push(xx);
  for(let k=0;k<joints.length-1;k++){
   const l=joints[k],r=joints[k+1],bw=r-l;if(bw<7*scale||bw>500*scale)continue;
   for(let b=y+Math.round(7*scale);b<Math.min(h-20,y+100*scale);b++){
    if(!dark(l,b)||!dark(r,b)||!horizontal(l,b,bw))continue;
    const bh=b-y;if(!vertical(l,y,bh)||!vertical(r,y,bh))continue;
    let ink=0,total=0;const pad=Math.max(3,Math.round(2*scale));
    for(let yy=y+pad;yy<b-pad;yy+=2)for(let xx=l+pad;xx<r-pad;xx+=2){total++;if(dark(xx,yy))ink++;}
    if(total&&ink/total<.025){let z={x:l/scale,y:y/scale,w:bw/scale,h:bh/scale};if(!boxes.some(a=>Math.abs(a.x-z.x)<3&&Math.abs(a.y-z.y)<3))boxes.push(z);}
    break;
   }
  }
  x=e;
 }
 return boxes;
}
// Printed entry lines are often drawing commands, not underscore characters.
// Ground candidates in a short field label so rules in diagrams and paragraphs
// do not become editable fields.
const ENTRY_LABEL = /^(?:(?:client|customer|company|supplier|contact|first|last|full)\s+)?(?:name|customer|client|address|e[ -]?mail(?: address)?|telephone|phone(?: number)?|mobile(?: number)?|fax(?: number)?|contact person|role of signatory|job title|position|machine|model|serial(?: number| no\.?)?|date(?: and time)?|time and place|place|signature(?: and name)?|signed by|print(?:ed)? name)\s*:?$/i;
function shortLabel(text){
 return text.replace(/[_…]{2,}.*$/, '').replace(/\.{4,}.*$/, '').trim();
}
// Find the blank cell to the right of a label, including tables whose outer
// edge is open. Use both row rules and a continuous column divider; never use
// the label's varying text width as the start of a table entry.
export function findGridEntries(items,canvas,width,height){
 if(!canvas)return [];
 const scale=canvas.width/width,cw=canvas.width,ch=canvas.height;
 const data=canvas.getContext('2d',{willReadFrequently:true}).getImageData(0,0,cw,ch).data;
 const dark=(x,y)=>{if(x<0||x>=cw||y<0||y>=ch)return false;const k=(y*cw+x)*4;return data[k]<235&&data[k+1]<235&&data[k+2]<235;};
 function ruleAt(x,y){
  if(!dark(x,y))return null;
  let l=x,r=x;
  while(l>0&&(dark(l-1,y)||dark(l-2,y)))l--;
  while(r<cw-1&&(dark(r+1,y)||dark(r+2,y)))r++;
  return r-l>=70*scale?{l,r,y}:null;
 }
 const fields=[];
 for(const t of items){
  const label=shortLabel(t.text);if(!ENTRY_LABEL.test(label)||t.y<height*.07||t.y+t.h>height*.93)continue;
  const sample=Math.round((t.x+Math.min(t.w/2,12))*scale);
  let top=null,bottom=null;
  for(let y=Math.floor((t.y+1)*scale);y>=Math.max(0,(t.y-28)*scale);y--){const r=ruleAt(sample,y);if(r){top=r;break;}}
  for(let y=Math.ceil((t.y+t.h-1)*scale);y<Math.min(ch,(t.y+t.h+28)*scale);y++){const r=ruleAt(sample,y);if(r){bottom=r;break;}}
  if(!top||!bottom||bottom.y-top.y<12*scale||bottom.y-top.y>75*scale)continue;
  const left=Math.max(top.l,bottom.l),end=Math.min(top.r,bottom.r);
  if(end-left<90*scale)continue;
  let divider=null;
  for(let x=Math.ceil((t.x+t.w+2)*scale);x<end-40*scale;x++){
   let ink=0,total=0;
   for(let y=top.y+2;y<bottom.y-1;y++){total++;if(dark(x,y)||dark(x-1,y)||dark(x+1,y))ink++;}
   if(total&&ink/total>.9){divider=x;break;}
  }
  if(divider===null)continue;
  // Use the first divider after the label and stop at the next cell boundary.
  let right=end;
  for(let x=divider+Math.ceil(5*scale);x<end-2*scale;x++){
   let ink=0,total=0;for(let y=top.y+2;y<bottom.y-1;y++){total++;if(dark(x,y)||dark(x-1,y)||dark(x+1,y))ink++;}
   if(total&&ink/total>.9){right=x;break;}
  }
  const pad=3,f={x:divider/scale+pad,y:top.y/scale+pad,w:(right-divider)/scale-pad*2,h:(bottom.y-top.y)/scale-pad*2,label,type:/signature|signed by/i.test(label)?'signature':/date|time and place/i.test(label)?'date':'text',sourceY:t.y};
  if(f.w<35||f.h<5)continue;
  if(items.some(a=>a!==t&&a.text.trim()&&a.x+a.w/2>f.x&&a.x+a.w/2<f.x+f.w&&a.y+a.h/2>f.y&&a.y+a.h/2<f.y+f.h))continue;
  if(!fields.some(a=>Math.abs(a.x-f.x)<5&&Math.abs(a.y-f.y)<5))fields.push(f);
 }
 return fields;
}
export function findLabelledLines(items,canvas,width,height){
 if(!canvas)return [];
 const scale=canvas.width/width,cw=canvas.width,ch=canvas.height;
 const data=canvas.getContext('2d',{willReadFrequently:true}).getImageData(0,0,cw,ch).data;
 const dark=(x,y)=>{if(x<0||x>=cw||y<0||y>=ch)return false;let k=(y*cw+x)*4;return data[k]<225&&data[k+1]<225&&data[k+2]<225;};
 const gridFields=findGridEntries(items,canvas,width,height),fields=gridFields.slice();
 for(const t of items){
  if(gridFields.some(f=>Math.abs(f.sourceY-t.y)<2&&f.label===shortLabel(t.text)))continue;
  let label=shortLabel(t.text);
  if(!ENTRY_LABEL.test(label)||t.y<height*.07||t.y+t.h>height*.93)continue;
  let endOfLabel=t.x+t.w;
  if(label!==t.text.trim())endOfLabel=t.x+t.w*Math.min(1,label.length/t.text.length);
  // PDF extractors sometimes split "Signature and name" across text runs.
  if(/^signature/i.test(label)){
   const parts=items.filter(a=>Math.abs(a.y-t.y)<3&&a.x>t.x&&a.x<t.x+155&&/^(and|name)$/i.test(a.text.trim()));
   if(parts.length){endOfLabel=Math.max(endOfLabel,...parts.map(a=>a.x+a.w));label='Signature and name';}
  }
  const right=items.filter(a=>a!==t&&Math.abs(a.y-t.y)<Math.max(4,t.h*.4)&&a.x>endOfLabel+3&&a.text.trim()&&!/^[_ .…]+$/.test(a.text)).sort((a,b)=>a.x-b.x)[0];
  const left=Math.max(0,Math.floor((endOfLabel-3)*scale)),rightLimit=Math.min(cw-1,Math.floor((right?right.x-4:width-15)*scale));
  let best=null;
  for(let y=Math.max(0,Math.floor((t.y+t.h*.6)*scale));y<Math.min(ch,Math.ceil((t.y+t.h+7)*scale));y++){
   for(let x=left;x<Math.min(rightLimit,(endOfLabel+26)*scale);x++){
    if(!dark(x,y))continue;const start=x;let last=x,gap=0;
    for(;x<rightLimit;x++){
     if(dark(x,y)){last=x;gap=0;}else if(++gap>Math.max(2,scale*1.3))break;
    }
    const len=(last-start)/scale;
    if(len<40||start/scale>endOfLabel+24)continue;
    const f={x:start/scale+1,y:y/scale-Math.max(15,t.h+3),w:len-2,h:Math.max(15,t.h+3),label,type:/signature|signed by/i.test(label)?'signature':/date|time and place/i.test(label)?'date':'text'};
    // An occupied cell is not a blank entry line.
    if(items.some(a=>a!==t&&a.text.trim()&&!/^[_ .…]+$/.test(a.text)&&a.x+a.w/2>f.x+2&&a.x+a.w/2<f.x+f.w-2&&a.y+a.h/2>f.y&&a.y+a.h/2<f.y+f.h-2))continue;
    if(!best||f.w>best.w+2||(Math.abs(f.w-best.w)<2&&f.y<best.y))best=f;
   }
  }
  if(best&&!fields.some(f=>Math.abs(f.x-best.x)<5&&Math.abs(f.y-best.y)<5))fields.push(best);
 }
 return fields;
}
export function detectPage(items,boxes,width,height,native=[],canvas=null){
 const full=items.map(t=>t.text).join(' '),top=items.filter(t=>t.y<height*.22).map(t=>t.text).join(' ');
 const toc=/\bcontents\b/i.test(top)||(/(?:\.\s*){5}/.test(full)&&full.length>1800);
 const checks=boxes.filter(b=>b.w>=8&&b.w<=42&&b.h>=8&&b.h<=46&&b.y<height*.92&&Math.min(b.w,b.h)/Math.max(b.w,b.h)>.45&&!items.some(t=>t.text.trim()&&!/^[\[\]\s☐□\uF0A3\uF0A8]+$/.test(t.text)&&b.x+b.w/2>t.x&&b.x+b.w/2<t.x+t.w&&b.y+b.h/2>t.y&&b.y+b.h/2<t.y+t.h));
 const printed=items.filter(t=>/\[\s*\]|☐|□|\uF0A3|\uF0A8/.test(t.text));
 const heading=/\b(check\s*list|checklist|form\s*[-–:]|application form|consent form)\b/i.test(top);
 const signatureItems=items.filter(t=>/^(signatures?|signature and(?: name)?|customer signature|client signature|authorized signature|signed by|sign here)\s*[:.]?$/i.test(t.text.trim()));
 const signature=signatureItems.length>0;
 const aligned=checks.some(b=>checks.filter(a=>Math.abs(a.x-b.x)<5&&Math.abs(a.y-b.y)>8).length>=2);
 const checkboxPage=(printed.length>=3||(checks.length>=3&&aligned))&&/customer|client|prepared|available|select|yes|no|complete|check/i.test(full);
 const ruledFields=findLabelledLines(items,canvas,width,height);
 const contactPage=ruledFields.length>=2||ruledFields.some(f=>f.type==='signature');
 const matched=!toc&&(native.length>0||heading||signature||checkboxPage||contactPage);
 let fields=native.slice(),add=(type,b,label,value='')=>{
  const f={id:(crypto.randomUUID?.()||'f'+Math.random().toString(36).slice(2)),type,x:Math.max(0,b.x),y:Math.max(0,b.y),w:Math.min(b.w,width-b.x),h:Math.min(b.h,height-b.y),label,value};
  if(f.w<5||f.h<5)return;
  if(fields.some(a=>{const ix=Math.max(0,Math.min(a.x+a.w,f.x+f.w)-Math.max(a.x,f.x)),iy=Math.max(0,Math.min(a.y+a.h,f.y+f.h)-Math.max(a.y,f.y));return ix*iy/Math.min(a.w*a.h,f.w*f.h)>.55;}))return;
  fields.push(f);
 };
 if(matched){
  ruledFields.forEach(f=>add(f.type,f,f.label));
  checks.forEach((b,i)=>add('check',{x:b.x+(b.w-Math.min(14,b.w-2))/2,y:b.y+(b.h-Math.min(14,b.h-2))/2,w:Math.min(14,b.w-2),h:Math.min(14,b.h-2)},`Checklist response ${i+1}`,false));
  printed.forEach((t,i)=>{const match=t.text.match(/\[\s*\]|☐|□|\uF0A3|\uF0A8/);const pos=match.index/t.text.length;add('check',{x:t.x+t.w*pos,y:t.y,w:Math.min(12,t.h),h:Math.min(12,t.h)},`Checkbox ${i+1}`,false);});
  boxes.filter(b=>b.w>42&&b.h<100&&!items.some(t=>t.x+t.w/2>b.x+2&&t.x+t.w/2<b.x+b.w-2&&t.y+t.h/2>b.y+2&&t.y+t.h/2<b.y+b.h-2)).forEach((b,i)=>{
   const near=items.filter(t=>Math.abs(t.y-b.y)<b.h+5&&t.x<b.x).sort((a,c)=>Math.abs(a.y-b.y)-Math.abs(c.y-b.y))[0];
   let label=near?.text?.trim()||`Entry ${i+1}`;let type=/signature/i.test(label)?'signature':/date|time and place/i.test(label)?'date':'text';
   add(type,{x:b.x+3,y:b.y+2,w:b.w-6,h:b.h-4},label);
  });
  items.forEach(t=>{
   let re=/_{3,}|\.{5,}|…{2,}/g,m;while((m=re.exec(t.text))){const char=t.w/Math.max(t.text.length,1);add('text',{x:t.x+m.index*char,y:t.y-1,w:Math.max(30,m[0].length*char),h:Math.max(13,t.h+3)},'Blank entry');}
   const label=t.text.trim();
   if(/^(client name|customer|machine|contact person|role of signatory|address|telephone|phone|e-?mail|name|place|date|date and time|time and place|signature|signature and|signature and name|in block letters|client)\s*:?$/i.test(label)&&t.y>height*.08&&t.y<height*.9){
    if(/^client$/i.test(label)&&!signature)return;
    if(/^(name|in block letters)$/i.test(label)&&items.some(a=>/^signature/i.test(a.text)&&Math.abs(a.y-t.y)<35))return;
    if(fields.some(f=>f.type!=='check'&&Math.abs(f.y-t.y)<8&&f.x>t.x+t.w-2))return;
    let right=items.filter(a=>Math.abs(a.y-t.y)<5&&a.x>t.x+t.w+3).sort((a,b)=>a.x-b.x)[0];
    let x=t.x+t.w+9;
    if(/^signature/i.test(label)){const parts=items.filter(a=>Math.abs(a.y-t.y)<3&&a.x>t.x&&a.x<t.x+150&&/^(and|name)$/i.test(a.text.trim()));if(parts.length){x=Math.max(...parts.map(a=>a.x+a.w))+9;right=null;}}
    if(canvas&&!right){const scale=canvas.width/width,ctx=canvas.getContext('2d'),data=ctx.getImageData(0,0,canvas.width,canvas.height).data;for(let xx=Math.ceil(x*scale);xx<Math.min(width*.55,x+90)*scale;xx++){let ink=0,total=0;for(let yy=Math.ceil((t.y+3)*scale);yy<(t.y+t.h-1)*scale;yy++){total++;let k=(yy*canvas.width+xx)*4;if(data[k]<200&&data[k+1]<200&&data[k+2]<200)ink++;}if(total&&ink/total>.9){x=xx/scale+4;break;}}}
    const end=right?right.x-5:width-58;
    add(/signature|^client$/i.test(label)?'signature':/date|time and place/i.test(label)?'date':'text',{x,y:t.y-2,w:Math.min(end-x,500),h:Math.max(t.h+5,15)},label.replace(/:$/,''));
   }
  });
  signatureItems.filter(t=>/^signatures$/i.test(t.text.trim())).forEach(t=>{
   const later=items.filter(a=>a.y>t.y+15&&a.y<height*.9&&/^Client$/i.test(a.text.trim()));
   if(!later.length)add('signature',{x:t.x,y:t.y+20,w:Math.min(250,width-t.x-50),h:32},'Signature');
  });
 }
 fields=fields.sort((a,b)=>a.y-b.y||a.x-b.x);
 return {matched,fields,reason:native.length?'Existing form fields':heading?'Checklist / form':signature?'Signature area':checkboxPage?'Checklist responses':contactPage?'Contact / entry lines':'No form cues',toc};
}
