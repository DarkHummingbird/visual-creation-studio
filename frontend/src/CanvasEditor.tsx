import React,{useState,useEffect,useRef} from 'react';
import {Stage,Layer,Image as KImage,Text,Rect,Transformer,Group,Ellipse,Star,Arrow,Line} from 'react-konva';
import {api,uuid,ask} from './api';import pagePresets from './pagePresets';

export const FONTS=[
 {k:'hei',label:'现代黑体',stack:'"PingFang SC","Microsoft YaHei",sans-serif'},
 {k:'song',label:'宋体衬线',stack:'"Songti SC","SimSun",serif'},
 {k:'round',label:'圆体',stack:'"Yuanti SC","Arial Rounded MT Bold",sans-serif'},
 {k:'hand',label:'手写体',stack:'"Xingkai SC","Kaiti SC","KaiTi",cursive'}];
const fontStack=(k:string)=>FONTS.find(f=>f.k===k)?.stack||FONTS[0].stack;
export const TEXT_PRESETS:any={
 title:{label:'主标题',fontSize:64,bold:true,color:'#17212b',shadow:true,stroke:null},
 sub:{label:'副标题',fontSize:36,bold:false,color:'#4c5b6b',shadow:false,stroke:null},
 price:{label:'价格',fontSize:80,bold:true,color:'#d4393b',shadow:true,stroke:null},
 tag:{label:'标签字',fontSize:34,bold:true,color:'#ffffff',shadow:false,stroke:{color:'#00000055',width:2}}};
export const STICKERS=[
 {id:'badge',label:'圆角标签',text:'新品上市',color:'#e8452c',textColor:'#ffffff'},
 {id:'bubble',label:'气泡',text:'店长推荐',color:'#2861c3',textColor:'#ffffff'},
 {id:'burst',label:'星爆',text:'限时特惠',color:'#f6a723',textColor:'#ffffff'},
 {id:'coupon',label:'优惠券',text:'满100减20',color:'#d4393b',textColor:'#ffffff'},
 {id:'arrow',label:'箭头',text:'点我抢购',color:'#2fa36b',textColor:'#ffffff'},
 {id:'ribbon',label:'横幅',text:'全场包邮',color:'#25384b',textColor:'#ffffff'}];
const darker=(hex:string,f=0.75)=>{const n=parseInt(hex.slice(1),16);return '#'+[16,8,0].map(s=>Math.round(((n>>s)&255)*f).toString(16).padStart(2,'0')).join('')};

function StickerShape({item,bgfill}:{item:any,bgfill:string}){
 const w=item.width,h=item.height,c=item.color||'#e8452c';
 const shadow={shadowColor:'rgba(0,0,0,.28)',shadowBlur:10,shadowOffsetY:4,shadowOpacity:.8};
 const fs=Math.max(13,Math.round(h*(item.shape==='burst'?0.3:0.34)));
 if(item.shape==='bubble')return <><Ellipse x={w/2} y={h/2} radiusX={w/2} radiusY={h/2} fill={c} {...shadow}/><Text width={w} height={h} text={item.text} fontSize={fs} fontFamily={fontStack(item.font||'hei')} fontStyle="bold" fill={item.textColor||'#fff'} align="center" verticalAlign="middle" listening={false}/></>;
 if(item.shape==='burst')return <><Star x={w/2} y={h/2} numPoints={11} innerRadius={h*0.33} outerRadius={Math.min(w,h)*0.5} fill={c} {...shadow}/><Text width={w} height={h*0.72} y={h*0.14} text={item.text} fontSize={fs} fontFamily={fontStack(item.font||'hei')} fontStyle="bold" fill={item.textColor||'#fff'} align="center" verticalAlign="middle" listening={false}/></>;
 if(item.shape==='coupon')return <><Rect width={w} height={h} cornerRadius={10} fill={c} {...shadow}/><Ellipse x={0} y={h/2} radiusX={h*0.13} radiusY={h*0.13} fill={bgfill} listening={false}/><Ellipse x={w} y={h/2} radiusX={h*0.13} radiusY={h*0.13} fill={bgfill} listening={false}/><Text width={w} height={h} text={item.text} fontSize={fs} fontFamily={fontStack(item.font||'hei')} fontStyle="bold" fill={item.textColor||'#fff'} align="center" verticalAlign="middle" listening={false}/></>;
 if(item.shape==='arrow')return <><Arrow points={[4,h/2,w-4,h/2]} pointerLength={h*0.42} pointerWidth={h*0.72} fill={c} {...shadow}/><Text width={w*0.8} height={h} text={item.text} fontSize={fs} fontFamily={fontStack(item.font||'hei')} fontStyle="bold" fill={item.textColor||'#fff'} align="center" verticalAlign="middle" listening={false}/></>;
 if(item.shape==='ribbon')return <><Rect width={w} height={h} cornerRadius={4} fill={c} {...shadow}/><Line points={[0,h,w/2-8,h+10,0,h+10]} closed fill={darker(c)} listening={false}/><Line points={[w,h,w/2+8,h+10,w,h+10]} closed fill={darker(c)} listening={false}/><Text width={w} height={h} text={item.text} fontSize={fs} fontFamily={fontStack(item.font||'hei')} fontStyle="bold" fill={item.textColor||'#fff'} align="center" verticalAlign="middle" listening={false}/></>;
 return <><Rect width={w} height={h} cornerRadius={Math.min(14,h/3)} fill={c} {...shadow}/><Text width={w} height={h} text={item.text} fontSize={fs} fontFamily={fontStack(item.font||'hei')} fontStyle="bold" fill={item.textColor||'#fff'} align="center" verticalAlign="middle" listening={false}/></>;
}

function Shape({item,onSelect,onChange,selected,onSnap,bgfill}:any){
 const [image,setImage]=useState<HTMLImageElement>();const ref=useRef<any>(null),tr=useRef<any>(null);
 useEffect(()=>{if(item.type==='IMAGE'){let im=new window.Image();im.onload=()=>setImage(im);im.src='/media/'+item.assetId}},[item.assetId]);
 useEffect(()=>{if(selected&&tr.current&&ref.current){tr.current.nodes([ref.current]);tr.current.getLayer().batchDraw()}},[selected,image]);
 const props={...item,id:item.id,ref,onClick:onSelect,onTap:onSelect,draggable:!item.locked,
  onDragMove:(e:any)=>{if(!onSnap)return;const p=onSnap(e.target.position(),item);e.target.position({x:p.x,y:p.y})},
  onDragEnd:(e:any)=>{onSnap&&onSnap(null,null);onChange({...item,x:e.target.x(),y:e.target.y()})},
  onTransformEnd:()=>{let n=ref.current;let sx=n.scaleX(),sy=n.scaleY();n.scaleX(1);n.scaleY(1);onChange({...item,x:n.x(),y:n.y(),width:Math.max(10,item.width*sx),height:Math.max(10,item.height*sy),rotation:n.rotation()})}};
 const isSticker=item.type==='STICKER';
 return <>{isSticker?<Group {...props}><StickerShape item={item} bgfill={bgfill}/></Group>
  :item.type==='IMAGE'?<KImage {...props} image={image}/>
  :item.type==='TEXT'?<Text {...props} text={item.text} fill={item.color||'#17212b'} fontFamily={fontStack(item.font||'hei')} fontStyle={item.bold?'bold':'normal'} fontSize={item.fontSize||48} align={item.align||'left'} stroke={item.stroke?item.stroke.color:undefined} strokeWidth={item.stroke?item.stroke.width:0} strokeEnabled={!!item.stroke} shadowColor={item.shadow?'rgba(0,0,0,.3)':undefined} shadowBlur={item.shadow?8:0} shadowOffsetY={item.shadow?3:0} shadowOpacity={item.shadow?0.8:0}/>
  :<Rect {...props} fill={item.color||'#dddddd'}/>}{selected&&!item.locked&&<Transformer ref={tr} keepRatio={item.type==='IMAGE'||isSticker} rotateEnabled={true}/>}</>
}

export default function CanvasEditor({draft,onChange,assets,toast,flush}:{draft:any,onChange:any,assets:any[],toast:any,flush:any}){
 const doc=draft.data.canvas;const stage=useRef<any>(null);const [selected,select]=useState('');const [history,H]=useState<any[]>([]),[future,F]=useState<any[]>([]);const [imageId,I]=useState('');const [edit,E]=useState('');const [stickerId,ST]=useState(STICKERS[0].id);const [guides,G]=useState<any>({v:[],h:[]});const [bgCanvas,BC]=useState<any>(null);const [suggest,SG]=useState<string[]>([]);
 const scale=Math.min(620/doc.width,560/doc.height);
 const set=(d:any,record=true)=>{if(record){H(h=>[...h.slice(-99),structuredClone(doc)]);F([])}onChange({...draft.data,canvas:d})};
 const picked=doc.layers.find((x:any)=>x.id===selected);const patch=(v:any)=>set({...doc,layers:doc.layers.map((x:any)=>x.id===v.id?v:x)});
 const snap=(pos:any,layer:any)=>{
  if(!pos){G({v:[],h:[]});return null}
  const thr=6;let{x,y}=pos;const v:number[]=[],h:number[]=[];
  const xs=[0,doc.width/2,doc.width],ys=[0,doc.height/2,doc.height];
  for(const g of xs){if(Math.abs(x-g)<thr){x=g;v.push(g)}else if(Math.abs(x+layer.width/2-g)<thr){x=g-layer.width/2;v.push(g)}else if(Math.abs(x+layer.width-g)<thr){x=g-layer.width;v.push(g)}}
  for(const o of doc.layers){if(o.id===layer.id||o.visible===false)continue;if(Math.abs(x+layer.width/2-(o.x+o.width/2))<thr){x=o.x+o.width/2-layer.width/2;v.push(o.x+o.width/2)}}
  for(const g of ys){if(Math.abs(y-g)<thr){y=g;h.push(g)}else if(Math.abs(y+layer.height/2-g)<thr){y=g-layer.height/2;h.push(g)}else if(Math.abs(y+layer.height-g)<thr){y=g-layer.height;h.push(g)}}
  for(const o of doc.layers){if(o.id===layer.id||o.visible===false)continue;if(Math.abs(y+layer.height/2-(o.y+o.height/2))<thr){y=o.y+o.height/2-layer.height/2;h.push(o.y+o.height/2)}}
  G({v:[...new Set(v)],h:[...new Set(h)]});return{x,y}};
 const center=(axis:string)=>{if(!picked)return;patch({...picked,x:axis==='x'?(doc.width-picked.width)/2:picked.x,y:axis==='y'?(doc.height-picked.height)/2:picked.y})};
 const add=(type:string)=>{
  if(type==='STICKER'){const st=STICKERS.find(s=>s.id===stickerId)||STICKERS[0];const w=doc.width*0.42,h=doc.height*0.16;
   set({...doc,layers:[...doc.layers,{id:uuid(),type:'STICKER',shape:st.id,text:st.text,color:st.color,textColor:st.textColor,font:'hei',x:(doc.width-w)/2,y:60,width:w,height:h,rotation:st.id==='ribbon'?-3:0,locked:false,visible:true}]});return}
  const im=assets.find(a=>a.id===imageId);if(type==='IMAGE'&&!im)return toast('先选择图片');let ratio=im?im.meta.width/im.meta.height:1;let w=type==='IMAGE'?Math.min(doc.width,doc.height*ratio):doc.width*.8;let h=type==='IMAGE'?w/ratio:100;
  if(type==='TEXT'){const p=TEXT_PRESETS.title;set({...doc,layers:[...doc.layers,{id:uuid(),type:'TEXT',text:'双击左侧编辑文字',font:'hei',bold:p.bold,shadow:p.shadow,stroke:p.stroke,align:'left',color:p.color,fontSize:p.fontSize,x:60,y:60,width:w,height:h*1.2,rotation:0,locked:false,visible:true}]});return}
  set({...doc,layers:[...doc.layers,{id:uuid(),type,assetId:type==='IMAGE'?imageId:undefined,text:'',fontSize:48,color:'#17212b',x:type==='IMAGE'?(doc.width-w)/2:60,y:type==='IMAGE'?(doc.height-h)/2:60,width:w,height:h,rotation:0,locked:false,visible:true}]});};
 const bg=doc.bg||{type:'white',color1:'#f5f0e8',color2:'#e8dcc8'};
 const setBg=(k:string,v:any)=>set({...doc,bg:{...bg,[k]:v}});
 useEffect(()=>{
  if(bg.type!=='blur'){BC(null);return}
  const layer=doc.layers.find((l:any)=>l.type==='IMAGE'&&l.visible!==false);if(!layer){BC(null);return}
  let alive=true;const im=new window.Image();im.onload=()=>{if(!alive)return;const cv=document.createElement('canvas');cv.width=doc.width;cv.height=doc.height;const ctx=cv.getContext('2d')!;const f=Math.max(doc.width/im.width,doc.height/im.height);ctx.filter='blur(24px) brightness(.92)';ctx.drawImage(im,(doc.width-im.width*f)/2,(doc.height-im.height*f)/2,im.width*f,im.height*f);BC(cv)};im.src='/media/'+layer.assetId;
  return()=>{alive=false};
 },[bg.type,bg.color1,doc.layers,doc.width,doc.height]);
 const bgNode=bg.type==='color'?<Rect x={0} y={0} width={doc.width} height={doc.height} fill={bg.color1} listening={false}/>
  :bg.type==='gradient'?<Rect x={0} y={0} width={doc.width} height={doc.height} fillLinearGradientStartPoint={{x:0,y:0}} fillLinearGradientEndPoint={{x:0,y:doc.height}} fillLinearGradientColorStops={[0,bg.color1,1,bg.color2]} listening={false}/>
  :bg.type==='blur'&&bgCanvas?<KImage image={bgCanvas} width={doc.width} height={doc.height} listening={false}/>:<Rect x={0} y={0} width={doc.width} height={doc.height} fill="white" listening={false}/>;
 const resize=(w:number,h:number,mode='CONTAIN')=>{if(w<200||h<200||w>4096||h>4096)return toast('尺寸请在200至4096像素之间');let sx=w/doc.width,sy=h/doc.height;const old=structuredClone(doc);let factor=mode==='COVER'?Math.max(sx,sy):Math.min(sx,sy);set({width:w,height:h,layers:doc.layers.map((x:any)=>({...x,x:x.x*factor+(w-doc.width*factor)/2,y:x.y*factor+(h-doc.height*factor)/2,width:x.width*factor,height:x.height*factor,fontSize:x.fontSize?x.fontSize*factor:undefined})),variants:[...(doc.variants||[]),{...old,variants:undefined}]})};
 const exportImage=async()=>{try{select('');await new Promise(r=>setTimeout(r,70));let bad=doc.layers.find((x:any)=>x.type==='TEXT'&&(x.x<0||x.y<0||x.x+x.width>doc.width||x.y+x.height>doc.height));if(bad)return toast('文字层超出画布，请调整位置与边界');await flush();const rendered=stage.current.toCanvas({pixelRatio:1/scale});const output=document.createElement('canvas');output.width=doc.width;output.height=doc.height;output.getContext('2d')!.drawImage(rendered,0,0,doc.width,doc.height);let data=output.toDataURL('image/png');let a=await api('/drafts/'+draft.id+'/export-canvas',{data,width:doc.width,height:doc.height});window.open('/media/'+a.id+'?download=true');toast('图片已导出，草稿保留')}catch(e:any){toast(e.message)}};
 const aiCopy=async()=>{const p=draft.data.product||{};if(!p.name?.trim())return toast('请先在第1步填写商品名称');if(!await ask('将付费调用文字模型（约0.01元）生成5条促销文案。继续？'))return;try{const r=await api('/copy-suggestions',{name:p.name,description:p.description||''});SG(r.suggestions||[]);if(!r.suggestions?.length)toast('没有生成可用文案')}catch(e:any){toast(e.message)}};
 const useCopy=(s:string)=>{if(picked?.type==='TEXT')patch({...picked,text:s});else{const p=TEXT_PRESETS.tag;const w=doc.width*.7,h=Math.round(p.fontSize*1.7);set({...doc,layers:[...doc.layers,{id:uuid(),type:'TEXT',text:s,font:'hei',bold:p.bold,shadow:p.shadow,stroke:p.stroke,align:'center',color:'#17212b',fontSize:p.fontSize,x:(doc.width-w)/2,y:doc.height-h-40,width:w,height:h,rotation:0,locked:false,visible:true}]})}SG([])};
 return <div><div className="toolbar"><select value={imageId} onChange={e=>I(e.target.value)}><option value="">选择一张素材</option>{assets.filter(x=>x.kind==='IMAGE').map(a=><option key={a.id} value={a.id}>{a.name} · {a.id.slice(0,5)}</option>)}</select>{imageId&&<img className="ref-thumb" src={'/media/'+imageId} alt="待添加素材预览"/>}<button onClick={()=>add('IMAGE')}>添加图片层</button><button onClick={()=>add('TEXT')}>添加文字层</button><select value={stickerId} onChange={e=>ST(e.target.value)}>{STICKERS.map(s=><option key={s.id} value={s.id}>{s.label} · {s.text}</option>)}</select><button onClick={()=>add('STICKER')}>添加贴纸</button><button disabled={!history.length} onClick={()=>{F(f=>[...f,doc]);let h=[...history];let last=h.pop();H(h);set(last,false)}}>撤销</button><button disabled={!future.length} onClick={()=>{H(h=>[...h,doc]);let f=[...future];let last=f.pop();F(f);set(last,false)}}>重做</button></div>
 <div className="canvas-layout"><aside className="panel"><h3>图层</h3>{doc.layers.map((x:any,i:number)=><button className={'layer-item '+(selected===x.id?'chosen':'')} key={x.id} onClick={()=>select(x.id)}>{i+1} · {x.type==='IMAGE'?'图片':x.type==='TEXT'?'文字':x.type==='STICKER'?'贴纸':'色块'}{x.locked?' 🔒':''}</button>)}{picked&&<><div className="toolbar">{picked.type!=='IMAGE'&&<><button onClick={()=>center('x')}>水平居中</button><button onClick={()=>center('y')}>垂直居中</button></>}</div>
 {picked.type==='TEXT'&&<><label>内容<textarea value={picked.text} onChange={e=>patch({...picked,text:e.target.value})}/></label>
 <label>排版角色<div className="toolbar">{Object.entries(TEXT_PRESETS).map(([k,p]:any)=><button key={k} onClick={()=>patch({...picked,fontSize:p.fontSize,bold:p.bold,color:p.color,shadow:p.shadow,stroke:p.stroke})}>{p.label}</button>)}</div></label>
 <label>字体<select value={picked.font||'hei'} onChange={e=>patch({...picked,font:e.target.value})}>{FONTS.map(f=><option key={f.k} value={f.k}>{f.label}</option>)}</select></label>
 <div className="two"><label>字号<input type="number" min="10" max="240" value={picked.fontSize} onChange={e=>patch({...picked,fontSize:+e.target.value})}/></label><label>颜色<input type="color" value={picked.color} onChange={e=>patch({...picked,color:e.target.value})}/></label></div>
 <label>对齐<select value={picked.align||'left'} onChange={e=>patch({...picked,align:e.target.value})}><option value="left">左对齐</option><option value="center">居中</option><option value="right">右对齐</option></select></label>
 <div className="two"><label className="check"><input type="checkbox" checked={!!picked.bold} onChange={e=>patch({...picked,bold:e.target.checked})}/>粗体</label><label className="check"><input type="checkbox" checked={!!picked.shadow} onChange={e=>patch({...picked,shadow:e.target.checked})}/>投影</label></div>
 <label className="check"><input type="checkbox" checked={!!picked.stroke} onChange={e=>patch({...picked,stroke:e.target.checked?{color:'#ffffff',width:4}:null})}/>描边（白边在照片背景上更清晰）</label>
 {picked.stroke&&<label>描边颜色<input type="color" value={picked.stroke.color} onChange={e=>patch({...picked,stroke:{...picked.stroke,color:e.target.value}})}/></label>}</>}
 {picked.type==='STICKER'&&<><label>文字<textarea value={picked.text} onChange={e=>patch({...picked,text:e.target.value})}/></label><div className="two"><label>底色<input type="color" value={picked.color} onChange={e=>patch({...picked,color:e.target.value})}/></label><label>字色<input type="color" value={picked.textColor||'#ffffff'} onChange={e=>patch({...picked,textColor:e.target.value})}/></label></div>
 <label>字体<select value={picked.font||'hei'} onChange={e=>patch({...picked,font:e.target.value})}>{FONTS.map(f=><option key={f.k} value={f.k}>{f.label}</option>)}</select></label></>}
 {picked.type==='SHAPE'&&<label>颜色<input type="color" value={picked.color} onChange={e=>patch({...picked,color:e.target.value})}/></label>}
 {picked.type==='IMAGE'&&<><textarea placeholder="只修改选中的图片层，例如换成浅色背景" value={edit} onChange={e=>E(e.target.value)}/><button onClick={async()=>{if(!edit.trim())return toast('填写修改要求');if(!await ask('将付费调用图像模型，只生成候选，不覆盖原图。继续？'))return;try{let saved=await flush();await api('/drafts/'+draft.id+'/runs',{kind:'editimage',mutationId:uuid(),baseVersion:saved.version,paidConsent:true,options:{assetId:picked.assetId,prompt:edit,slot:'layer-'+picked.id}});toast('改图开始，结果在下方候选中')}catch(e:any){toast(e.message)}}}>生成改图候选</button></>}
 <label><input type="checkbox" checked={picked.locked} onChange={e=>patch({...picked,locked:e.target.checked})}/>锁定图层</label>
 <div className="toolbar"><button onClick={()=>{let a=[...doc.layers],i=a.findIndex(x=>x.id===selected);if(i<a.length-1)[a[i],a[i+1]]=[a[i+1],a[i]];set({...doc,layers:a})}}>上移</button><button onClick={()=>{let a=[...doc.layers],i=a.findIndex(x=>x.id===selected);if(i>0)[a[i],a[i-1]]=[a[i-1],a[i]];set({...doc,layers:a})}}>下移</button><button onClick={()=>{set({...doc,layers:doc.layers.filter((x:any)=>x.id!==selected)});select('')}}>删除</button></div></>}
 <h3>背景</h3><select value={bg.type} onChange={e=>setBg('type',e.target.value)}><option value="white">纯白</option><option value="color">纯色</option><option value="gradient">渐变</option><option value="blur">商品图虚化</option></select>{bg.type!=='white'&&bg.type!=='blur'&&<label>颜色<input type="color" value={bg.color1} onChange={e=>setBg('color1',e.target.value)}/></label>}{bg.type==='gradient'&&<label>颜色2<input type="color" value={bg.color2} onChange={e=>setBg('color2',e.target.value)}/></label>}{bg.type==='blur'&&<p className="hint">取画布第一张图片，模糊压暗后垫底。</p>}
 <h3>AI 文案</h3><button onClick={aiCopy}>基于商品资料生成5条</button>{suggest.map(s=><button className="layer-item" key={s} onClick={()=>useCopy(s)}>{s}</button>)}
 <h3>画布尺寸</h3><select defaultValue="" onChange={e=>{let p=pagePresets[+e.target.value];if(p)resize(p.width,p.height)}}><option value="" disabled>选择尺寸预设</option>{pagePresets.map((p,i)=><option key={i} value={i}>{p.name} {p.width}×{p.height}</option>)}</select><div className="toolbar"><input aria-label="画布宽度" type="number" value={doc.width} onChange={e=>resize(+e.target.value,doc.height)}/><input aria-label="画布高度" type="number" value={doc.height} onChange={e=>resize(doc.width,+e.target.value)}/></div><button onClick={()=>resize(doc.height,doc.width,'COVER')}>交换宽高并等比裁切</button><p className="hint">默认等比留白。图片不会非等比拉伸。尺寸变更保留旧布局。</p>{doc.variants?.length>0&&<select defaultValue="" onChange={e=>{let v=doc.variants[+e.target.value];if(v)set({...v,variants:doc.variants})}}><option value="">恢复已有尺寸布局</option>{doc.variants.map((v:any,i:number)=><option value={i} key={i}>{i+1} · {v.width}×{v.height}</option>)}</select>}</aside>
 <div className="canvas-area"><Stage width={doc.width*scale} height={doc.height*scale} scaleX={scale} scaleY={scale} ref={stage} onMouseDown={e=>{if(e.target===e.target.getStage())select('')}}><Layer>{bgNode}{doc.layers.filter((x:any)=>x.visible!==false).map((x:any)=><Shape key={x.id} item={x} selected={selected===x.id} onSelect={()=>select(x.id)} onChange={patch} onSnap={snap} bgfill={bg.type==='color'?bg.color1:bg.type==='blur'?'#e8ebf0':'#ffffff'}/>)}</Layer><Layer listening={false}>{guides.v.map((x:number,i:number)=><Line key={'v'+i} points={[x,0,x,doc.height]} stroke="#2861c3" strokeWidth={1} dash={[4,4]}/>)}{guides.h.map((y:number,i:number)=><Line key={'h'+i} points={[0,y,doc.width,y]} stroke="#2861c3" strokeWidth={1} dash={[4,4]}/>)}</Layer></Stage><p className="hint">拖动图层时蓝色参考线自动吸附对齐。{doc.width} × {doc.height} px</p></div></div><button className="primary" onClick={exportImage}>导出当前尺寸 PNG</button><p className="hint">逐个调整尺寸并导出，也可在“导出”页打包所有成品。</p></div>
}
