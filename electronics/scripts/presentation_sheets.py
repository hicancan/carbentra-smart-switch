#!/usr/bin/env python3
"""Three source-faithful presentation sheets; all rendered assets stay in ROOT/presentation."""
from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from local_runtime import runtime, configure_cycles, memory_kib, drawing_font

import subprocess,os,hashlib,json,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'electronics';O=ROOT/'presentation';RAW=O/'electronics_sources';RAW.mkdir(parents=True,exist_ok=True)
ENV=os.environ.copy()
for key,dr in [('XDG_CACHE_HOME','cache'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data')]:
 p=runtime()/dr;p.mkdir(parents=True,exist_ok=True);ENV[key]=str(p)
ENV['OMP_NUM_THREADS']='1';ENV['OPENBLAS_NUM_THREADS']='1'
inputs=[E/(b+'.'+ext)for b in ['power','control']for ext in ['kicad_sch','kicad_pcb']];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs}
def run(a):subprocess.run(a,check=True,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
for board in ['power','control']:
 for layer in ['F.Cu','In1.Cu','In2.Cu','B.Cu','Edge.Cuts']:
  run(['kicad-cli','pcb','export','svg','--mode-single','--black-and-white','--exclude-drawing-sheet','--page-size-mode','2','--drill-shape-opt','2','-l',layer,'-o',str(RAW/f'{board}-{layer}.svg'),str(E/f'{board}.kicad_pcb')])
NS='http://www.w3.org/2000/svg';ET.register_namespace('',NS)
def q(s):return'{'+NS+'}'+s
def el(tag,**a):return ET.Element(q(tag),{k.replace('_','-'):str(v)for k,v in a.items()})
def add(r,tag,**a):x=el(tag,**a);r.append(x);return x
def text(r,x,y,s,size=35,color='#172536',weight=400,anchor='start'):
 a=add(r,'text',x=x,y=y,fill=color,font_family='Noto Sans CJK SC, sans-serif',font_size=size,font_weight=weight,text_anchor=anchor);a.text=s
EDGE='#DCE3E7';MUTED='#64737F'
def page(w,h,title,sub):
 r=el('svg',width=w,height=h,viewBox=f'0 0 {w} {h}',version='1.1');add(r,'rect',width=w,height=h,fill='white');text(r,85,140,title,92,weight=700);text(r,87,205,sub,30,MUTED);add(r,'line',x1=85,y1=248,x2=w-85,y2=248,stroke=EDGE,stroke_width=3);return r,add(r,'defs')
def load(d,name,file,color=None):
 r=ET.fromstring(file.read_text());g=add(d,'g',id=name)
 for c in list(r):g.append(c)
 if color:
  for n in g.iter():
   for k,v in list(n.attrib.items()):n.set(k,re.sub('#000000',color,v,flags=re.I))
 return r.attrib['viewBox']
def crop(r,sid,box,vp):
 x,y,w,h=box;a,b,c,d=vp;defs=r.find(q('defs'));cid='crop-'+str(len(defs));cp=add(defs,'clipPath',id=cid,clipPathUnits='userSpaceOnUse');add(cp,'rect',x=x,y=y,width=w,height=h);g=add(r,'g',clip_path=f'url(#{cid})');n=add(g,'svg',x=x,y=y,width=w,height=h,viewBox=f'{a} {b} {c} {d}',preserveAspectRatio='xMidYMid meet',overflow='hidden');add(n,'use',href='#'+sid)
def panel(r,x,y,w,h,t,s):
 text(r,x,y+54,t,52,weight=700);text(r,x,y+98,s,26,MUTED);add(r,'rect',x=x,y=y+125,width=w,height=h-125,fill='white',stroke=EDGE,stroke_width=2);return(x+22,y+150,w-44,h-180)
def save(r,name):
 s=RAW/(name+'.svg');p=O/(name+'.png');ET.ElementTree(r).write(s,encoding='utf-8',xml_declaration=True);run(['inkscape',str(s),'--export-type=png',f'--export-filename={p}','--export-width=4000','--export-background=#ffffff','--export-background-opacity=1']);return[str(s.relative_to(ROOT)),str(p.relative_to(ROOT))]
outputs=[]
r,d=page(4000,3040,'原理图 · 六个功能区','两张原生 KiCad 图纸的真实功能区裁切 · 220 V 带零线 / 三路独立通断 / 总用电量记录')
load(d,'power',RAW/'power.svg');load(d,'control',RAW/'control.svg');cols=[85,1400,2715];rows=[285,1645];pw=1200;ph=1320
b=panel(r,cols[0],rows[0],pw,ph,'01  输入保护与隔离电源','功率板 · 高分断熔丝 / 热保护 MOV / RECOM PSU')
crop(r,'power',b,(38,72,204,204))
b=panel(r,cols[1],rows[0],pw,ph,'02  三路继电器输出','功率板 · 常开触点 / 冷侧驱动 / 默认断开')
x,y,w,h=b;crop(r,'power',(x,y,w,h*.66),(322,72,205,182));text(r,x+20,y+h*.73,'八芯隔离冷侧板间连接 · J2',25,MUTED);crop(r,'power',(x,y+h*.76,w,h*.22),(411,359,72,58))
b=panel(r,cols[2],rows[0],pw,ph,'03  总能耗计量与隔离','MCP39F511A / 2 mΩ Kelvin 分流 / ISOW7821')
x,y,w,h=b;crop(r,'power',(x,y,w,h*.41),(558,69,174,85));crop(r,'power',(x,y+h*.43,w*.52,h*.33),(669,200,64,64));text(r,x+w*.56,y+h*.47,'热侧 H_* = 火线参考',24,MUTED);text(r,x+w*.56,y+h*.51,'冷侧 C_* = 隔离逻辑',24,MUTED);text(r,x+w*.56,y+h*.55,'UART + 3.3 V 隔离供电',24,MUTED);crop(r,'power',(x+w*.54,y+h*.58,w*.44,h*.18),(580,327,208,23));text(r,x+20,y+h*.83,'真实 RC / 去耦元件节选；完整参数见原生图纸',23,MUTED);crop(r,'power',(x,y+h*.85,w,h*.14),(568,423,225,23))
b=panel(r,cols[0],rows[1],pw,ph,'04  Wi-Fi 与 BLE 主控','控制板 · ESP32-C3-MINI-1 / 启动与复位支持')
x,y,w,h=b;crop(r,'control',(x,y,w,h*.76),(96,96,72,91));crop(r,'control',(x,y+h*.78,w,h*.2),(49,264,201,66))
b=panel(r,cols[1],rows[1],pw,ph,'05  冷侧供电与维护接口','控制板 · 3.3 V 稳压 / 编程触点 / 八芯连接')
crop(r,'control',b,(310,92,190,313))
b=panel(r,cols[2],rows[1],pw,ph,'06  三路本地按键','控制板 · 断网可用 / 独立上拉 / RC 滤波')
crop(r,'control',b,(573,93,204,153))
text(r,85,3002,'CARBENTRA SMART SWITCH A  /  未通电工程样机 · 完整原图在 electronics/*.kicad_sch',25,MUTED)
text(r,3915,3002,'真实电路源图 · 非安规认证或量产放行',25,MUTED,anchor='end');outputs.append(save(r,'electronics_01_schematic_regions'))
colors=['#BE3D3D','#72B66B','#C7812E','#4F81B6'];layers=['F.Cu','In1.Cu','In2.Cu','B.Cu'];titles=['顶层 F.Cu','内层一 In1.Cu','内层二 In2.Cu','底层 B.Cu']
for board,title,dim in [('power','功率板 · PCB 四层铜箔','68 × 64 × 1.6 mm · 带侧边安装避让槽 · 热冷铜箔隔离目标 8 mm'),('control','控制板 · PCB 四层铜箔','76 × 76 × 1.0 mm · 全冷侧 / 天线净空 / 背面连接器')]:
 r,d=page(4000,3560,title,dim+' · 四图统一顶视坐标，底层未镜像')
 views=[]
 for l,c in zip(layers,colors):views.append(load(d,'cu-'+l,RAW/f'{board}-{l}.svg',c))
 edge=load(d,'edge',RAW/f'{board}-Edge.Cuts.svg','#BAC3CA');assert len(set(views+[edge]))==1;vp=tuple(map(float,edge.split()))
 for i,(l,t,c)in enumerate(zip(layers,titles,colors)):
  x=85+(i%2)*1980;y=295+(i//2)*1570;text(r,x,y+62,t,66,weight=700);text(r,x+1840,y+60,board+'.kicad_pcb',28,MUTED,anchor='end');box=(x+215,y+120,1450,1430);crop(r,'cu-'+l,box,vp);crop(r,'edge',box,vp)
 text(r,85,3498,'CARBENTRA SMART SWITCH A  /  '+board+' · 实际铜箔、焊盘、过孔及净空',28,MUTED);text(r,3915,3498,'ERC / DRC 通过不等于安全认证',28,MUTED,anchor='end');outputs.append(save(r,'electronics_02_'+board+'_four_layers'))
after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs};assert before==after
from PIL import Image
checks={}
for src,png in outputs:
 im=Image.open(ROOT/png);im.verify();im=Image.open(ROOT/png);checks[png]={'size':list(im.size),'opens':True,'sha256':hashlib.sha256((ROOT/png).read_bytes()).hexdigest()}
(E/'verification'/'presentation.json').write_text(json.dumps({'source_sha256':before,'source_unchanged':True,'outputs':outputs,'image_checks':checks,'notes':'Schematic panels crop native electrical drawings; dense metering passives are selected excerpts explicitly labeled. Both PCB four-layer panels show the complete actual board copper geometry.'},indent=2,ensure_ascii=False));print(json.dumps(checks,indent=2))
