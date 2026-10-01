#!/usr/bin/env python3
"""Typeset Chinese sheets and dimension page; composite and verify silent H.264."""
from pathlib import Path
from PIL import Image
import sys,subprocess,json,base64,html,os
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'presentation';WORK=OUT/'.work'
BG='#eef3ef';INK='#24484b';MUTED='#718b8b';ACC='#23836f';LINE='#8ca9a6'
def tx(x,y,t,size=31,color=INK):return f'<text x="{x}" y="{y}" fill="{color}" font-family="Noto Sans CJK SC, sans-serif" font-size="{size}">{html.escape(t)}</text>'
def im(path,x,y,w,h):return f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}"/>'
def start(w,h):return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',f'<rect width="{w}" height="{h}" fill="{BG}"/>']
def finish(items,name,w,pdf=False):
 p=OUT/(name+'.svg');p.write_text('\n'.join(items+['</svg>']))
 subprocess.run(['inkscape',str(p),'--export-filename='+str(OUT/(name+'.png')),'--export-width='+str(w)],check=True,capture_output=True)
 if pdf:subprocess.run(['inkscape',str(p),'--export-filename='+str(OUT/(name+'.pdf'))],check=True,capture_output=True)
if '--hero' in sys.argv or '--all' in sys.argv:
 # Technical alpha compositing only: preserve every rendered geometry pixel.
 rgba=Image.open(OUT/'model_01_exterior_hero.png').convert('RGBA')
 bg=Image.new('RGBA',rgba.size,(238,243,239,255));bg.alpha_composite(rgba)
 bg.convert('RGB').save(OUT/'model_01_exterior_hero_light.png')
if '--sheets' in sys.argv or '--all' in sys.argv:
 a=start(3600,2400);a+=[tx(120,105,'CARBENTRA / SW3',34),tx(120,156,'三键远程照明开关 · 六向正交视图',25,MUTED)]
 for i,(n,t) in enumerate(zip(['front','back','left','right','top','bottom'],['正面 / 操作面','背面 / 接线面','左侧','右侧','顶面','底面'])):
  x=1200*(i%3);y=180+1040*(i//3);a.append(im(OUT/'model_views'/f'{n}.png',x+140,y,920,920));a.append(tx(x+170,y+958,f'{i+1:02d}  {t}',30))
 a.append(tx(120,2340,'参考图仅用于外观方向；所有尺寸为独立工程提案，非原厂尺寸',23,MUTED));finish(a,'01_six_views',3600)
 a=start(3600,2240);a += [tx(110,96,'CARBENTRA / SW3',34),tx(110,149,'真实三维装配 · 结构分层示意',25,MUTED)]
 ix,iy,iw,ih=770,110,2060,2060;a.append(im(OUT/'model_03_exploded_assembly.png',ix,iy,iw,ih));anchors=json.loads((WORK/'anchors.json').read_text())
 calls=[('rockers','left',320,'三片独立瞬时摇臂','温白曲面 / 窄边框 / 本地按键'),('control','left',775,'隔离低压控制板','Wi-Fi + BLE / 本地离线控制'),('partition','left',1240,'独立绝缘防护隔板','标称厚度 1.8 mm / 材料等级待定'),('backbox','left',1780,'内嵌接线底壳','74 × 70 × 34 mm 工程提案'),('rim','right',320,'86 型窄边面框','86 × 86 mm / 无金属装饰边'),('radio','right',775,'ESP32-C3 无线模块','天线区禁布铜 / 禁放金属'),('relay','right',1240,'三路实体继电器','Omron G5Q-1A DC5 / 三路开关'),('psu','right',1780,'隔离电源与总路计量','RECOM 5 W / MCP39F511A')]
 for key,side,y,title,desc in calls:
  dash=' stroke-dasharray="12 10"' if key=='radio' else ''
  u,v=anchors[key];px=ix+u*iw;py=iy+v*ih
  if side=='left':x=105;sx=675;el=775;end=px-30
  else:x=2920;sx=2865;el=2785;end=px+30
  a.append(f'<path d="M {sx} {y+13} L {el} {y+13} L {end:.1f} {py:.1f} L {px:.1f} {py:.1f}" fill="none" stroke="{LINE}" stroke-width="2"{dash}/>');a.append(f'<circle cx="{px}" cy="{py}" r="7" fill="{ACC}"/>');a +=[tx(x,y,title,30),tx(x,y+53,desc,21,MUTED)]
 a += [tx(110,2108,'虚线引出为受上层组件遮挡的器件位置；所有组件来自同一装配模型',21,MUTED),tx(110,2165,'工程概念；带电安装、负载能力、计量精度、射频与安全认证均待实物验证',23,MUTED)]
 finish(a,'02_annotated_exploded',3600)
 # A vector dimension drawing, independent of raster rendering.
 a=start(1600,1080);a += [tx(75,83,'CARBENTRA / SW3',31),tx(75,128,'外形与叠层尺寸 / Proposed dimensions in mm',24,MUTED)]
 def ln(x1,y1,x2,y2,w=1.6,color=INK):return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}"/>'
 def rect(x,y,w,h,r=0,fill='white'):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{INK}" stroke-width="1.6"/>'
 def hd(x1,x2,y,ext,t):
  a.extend([ln(x1,ext,x1,y+10,.9,MUTED),ln(x2,ext,x2,y+10,.9,MUTED),ln(x1,y,x2,y),ln(x1-4,y+7,x1+4,y-7),ln(x2-4,y+7,x2+4,y-7),tx((x1+x2)/2-30,y-12,t,20)])
 def vd(y1,y2,x,ext,t):
  a.extend([ln(ext,y1,x-10,y1,.9,MUTED),ln(ext,y2,x-10,y2,.9,MUTED),ln(x,y1,x,y2),ln(x-7,y1+4,x+7,y1-4),ln(x-7,y2+4,x+7,y2-4),f'<text x="{x-17}" y="{(y1+y2)/2+25}" transform="rotate(-90 {x-17} {(y1+y2)/2+25})" fill="{INK}" font-family="Noto Sans CJK SC, sans-serif" font-size="20">{t}</text>'])
 sc=5;x,y=160,270;sz=86*sc;a.append(rect(x,y,sz,sz,9*sc));a.append(rect(x+3*sc,y+3*sc,80*sc,80*sc,7*sc))
 for xx in [x+(43-13.425)*sc,x+(43+13.425)*sc]:a.append(ln(xx,y+3*sc,xx,y+83*sc,.9))
 hd(x,x+sz,230,y,'86.0');vd(y,y+sz,105,x,'86.0');a.append(tx(265,805,'正面 / 三独立摇臂',22))
 # Side face projection is Z+; back box in wall Z-.
 sx,sy=855,270;a.append(rect(sx,sy,9.8*sc,86*sc,8));a.append(rect(sx+9.8*sc,sy+8*sc,34*sc,70*sc,12,fill='#dae6df'))
 a.append(ln(sx+9.8*sc,sy-50,sx+9.8*sc,sy+86*sc+50,.9,MUTED));a.append(tx(sx+9.8*sc-35,sy-65,'墙面',20,MUTED))
 hd(sx,sx+43.8*sc,230,sy,'43.8');hd(sx+9.8*sc,sx+43.8*sc,752,sy+78*sc,'34.0 入墙');a.append(tx(862,805,'右侧 / 安装基准面 Z=0',22))
 a += [tx(1190,284,'轴向叠层 / Z mm',23),tx(1190,327,'摇臂外表面     +9.8',19),tx(1190,365,'控制板         +3.2 ~ +4.2',19),tx(1190,403,'防护隔板       0 ~ +1.8',19),tx(1190,441,'电源顶部       -2.2',19),tx(1190,479,'继电器顶部     -8.2',19),tx(1190,517,'主功率板       -25.6 ~ -24',19),tx(1190,555,'底壳外表面     -34',19),tx(1190,621,'主板 68 × 64 × 1.6',19),tx(1190,659,'控制板 76 × 76 × 1.0',19)]
 a += [tx(75,893,'面板 86 × 86；底壳 74 × 70；紧固中心距 60（需按实物底盒确认）',22),tx(75,936,'建议预留净腔 ≥76 × 72 × 45，另核对接线弯曲空间；不能宣称适配全部 86 底盒',21),tx(75,991,'所有尺寸为独立设计提案。标称几何，无制造公差或材料阻燃/绝缘认证承诺。',20,MUTED),tx(75,1035,'2026-10-01 · 结构/铜箔/金属避让见工程说明；本页非生产放行图',18,MUTED)]
 finish(a,'model_dimensioned_layout',1600,pdf=True)
if '--video' in sys.argv or '--all' in sys.argv:
 ANIM=WORK/'animation';RGB=ANIM/'rgb';SEQ=ANIM/'sequence';RGB.mkdir(exist_ok=True);SEQ.mkdir(exist_ok=True);margins=[]
 for k in range(37):
  rgba=Image.open(ANIM/f'raw_{k:02d}.png').convert('RGBA');assert rgba.size==(1280,1280);b=rgba.getchannel('A').getbbox();assert b;mar=min(b[0],b[1],1280-b[2],1280-b[3]);assert mar>0;margins.append(mar)
  bg=Image.new('RGBA',rgba.size,(229,235,232,255));bg.alpha_composite(rgba);bg.convert('RGB').save(RGB/f'{k:02d}.png')
 states=[0]*24+list(range(1,37))+[36]*24+list(range(35,-1,-1))+[0]*24;assert len(states)==144
 for frame,k in enumerate(states):
  dst=SEQ/f'frame_{frame:04d}.png'
  if dst.exists():dst.unlink()
  os.link(RGB/f'{k:02d}.png',dst)
 output=OUT/'05_assembly_animation.mp4'
 subprocess.run(['ffmpeg','-y','-v','warning','-framerate','24','-i',str(SEQ/'frame_%04d.png'),'-c:v','libx264','-threads','2','-preset','medium','-crf','18','-pix_fmt','yuv420p','-r','24','-frames:v','144','-an','-movflags','+faststart',str(output)],check=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,pix_fmt','-of','json',str(output)]));v=probe['streams'][0]
 assert len(probe['streams'])==1 and (v['width'],v['height'],v['r_frame_rate'],v['codec_name'],v['nb_frames'])==(1280,1280,'24/1','h264','144') and float(probe['format']['duration'])==6
 subprocess.run(['ffmpeg','-v','error','-threads','2','-i',str(output),'-f','null','-'],check=True)
 (ROOT/'mechanical/verification/presentation_video_report.json').write_text(json.dumps({'probe':probe,'unique_real_3d_states':37,'minimum_alpha_edge_margin_px':min(margins),'first_last_assembled':True,'fully_decoded':True,'audio':False},indent=2))
 panel=Image.new('RGB',(1600,800),(229,235,232))
 for i,k in enumerate([0,8,20,36,36,20,8,0]):
  im1=Image.open(RGB/f'{k:02d}.png');im1.thumbnail((400,400));panel.paste(im1,((i%4)*400,(i//4)*400))
 panel.save(OUT/'model_animation_contact_sheet.jpg',quality=92)
print('COMPOSITION_READY')
