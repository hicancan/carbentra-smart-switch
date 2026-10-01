#!/usr/bin/env python3
"""Derive photographs, six orthographic views and 37 assembly states from one CAD.
All images are under root presentation/. No source geometry is overwritten.
"""
from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from local_runtime import runtime, configure_cycles, memory_kib, drawing_font

import sys,json,hashlib,time
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'presentation';WORK=OUT/'.work';ANIM=WORK/'animation';VIEWS=OUT/'model_views';MODEL=ROOT/'mechanical/carbentra_smart_switch.blend'
for p in [WORK,ANIM,VIEWS]:p.mkdir(exist_ok=True,parents=True)
sha=hashlib.sha256(MODEL.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(MODEL));s=bpy.context.scene;cam=s.camera
s.render.engine='CYCLES';configure_cycles(s);s.cycles.samples=12;s.cycles.use_denoising=True;s.cycles.use_auto_tile=True;s.cycles.tile_size=512
s.render.threads_mode='FIXED';s.render.threads=2;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA';s.render.film_transparent=True
bpy.context.preferences.filepaths.temporary_directory=str(runtime())
parts={o:(o.location.copy(),c.name) for c in bpy.data.collections if c.name!='Studio' for o in c.objects if o.type in {'MESH','CURVE','FONT'}}
def view(loc,target,scale,w=1280,h=1280):
 cam.location=Vector(loc);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;s.render.resolution_x=w;s.render.resolution_y=h
 q=cam.rotation_euler.to_quaternion()
 for name,co,power,size in [('Key softbox',(-.08,.095,.15),1.6,.13),('Rim softbox',(.09,.045,.09),.7,.1),('Front fill',(.01,-.07,.16),.35,.12)]:
  o=bpy.data.objects[name];o.location=Vector(target)+q@Vector(co);o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();o.data.energy=power;o.data.size=size
 bpy.context.view_layer.update()
def render(p):
 if p.exists():print('REUSE',p.name,flush=True);return
 s.render.filepath=str(p);t=time.monotonic();bpy.ops.render.render(write_still=True);print('RENDERED',p.name,'SECONDS',round(time.monotonic()-t,1),'RSS_KiB',memory_kib(),flush=True)
def state(k):
 u=(k/36)**2*(3-2*k/36)
 shifts={'01_Rockers':.078,'02_Face_Rim':.052,'03_Control_PCB':.040,'04_Isolation_Partition':.023,'05_Power_PCB':.010,'06_Backbox':0,'07_Fasteners':.052}
 for o,(loc,c) in parts.items():o.location=loc+Vector((0,0,(shifts[c]-.039)*u))
 bpy.context.view_layer.update()
if '--video' not in sys.argv:
 view((.13,-.175,.18),(0,0,-.008),.133);render(OUT/'model_01_exterior_hero.png')
 # View order: front means accessible rocker face, then actual rear and four edges.
 vs=[('front',(0,0,.20)),('back',(0,0,-.22)),('left',(-.20,0,-.012)),('right',(.20,0,-.012)),('top',(0,.20,-.012)),('bottom',(0,-.20,-.012))]
 for name,co in vs:view(co,(0,0,-.012),.111,900,900);render(VIEWS/(name+'.png'))
 # Real sectioned meshes only in memory; source stays assembled and complete.
 bpy.ops.mesh.primitive_cube_add(size=1,location=(0,-.062,-.005));tool=bpy.context.object;tool.dimensions=(.18,.125,.16);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);tool.hide_render=True
 mods=[]
 hidden=list(bpy.data.collections['01_Rockers'].objects)+[o for o in bpy.data.collections['03_Control_PCB'].objects if o.name=='control PCB legend']
 for o in hidden:o.hide_render=True
 for o in bpy.data.collections['03_Control_PCB'].objects:
  if o.name.startswith('Control PCB') or o.name.startswith('control actual '):
   mo=o.modifiers.new('Illustration half board section','BOOLEAN');mo.operation='DIFFERENCE';mo.object=tool;mods.append((o,mo))
 for c in ['01_Rockers','02_Face_Rim','04_Isolation_Partition','06_Backbox']:
  for o in bpy.data.collections[c].objects:
   if o.type=='MESH':mo=o.modifiers.new('Illustration half section','BOOLEAN');mo.operation='DIFFERENCE';mo.object=tool;mods.append((o,mo))
 view((.13,-.19,.14),(0,0,-.010),.134);render(OUT/'model_02_cutaway_internal.png')
 for o,mo in mods:o.modifiers.remove(mo)
 for o in hidden:o.hide_render=False
 bpy.data.objects.remove(tool,do_unlink=True)
 state(36);view((.135,-.22,.175),(0,0,-.006),.202,1600,1600);render(OUT/'model_03_exploded_assembly.png')
 anchors={}
 for key,p in {'rockers':(-.026,-.015,.0488),'rim':(-.041,-.025,.017),'radio':(0,.0315,.0066+.001),'control':(-.02,-.037,.0042+.001),'partition':(-.03,-.032,.0018-.016),'relay':(.02296,-.003,-.042),'psu':(-.012,-.03085,-.042),'backbox':(.025,-.035,-.030-.039)}.items():
  v=world_to_camera_view(s,cam,Vector(p));anchors[key]=[float(v.x),float(1-v.y)]
 (WORK/'anchors.json').write_text(json.dumps(anchors,indent=2));state(0)
if '--stills' not in sys.argv:
 view((.135,-.22,.175),(0,0,-.006),.202);s.render.fps=24
 # Render one fixed scene with true three-dimensional translated subassemblies.
 for k in range(37):state(k);render(ANIM/f'raw_{k:02d}.png')
 states=[0]*24+list(range(1,37))+[36]*24+list(range(35,-1,-1))+[0]*24
 s.frame_start=1;s.frame_end=144
 for frame,k in enumerate(states,1):
  state(k)
  for o in parts:o.keyframe_insert(data_path='location',frame=frame)
 s.frame_set(1);s['animation_notes']='6 seconds,24 fps,37 unique real3D states. Hold-open-hold-reassemble-hold. Silent.'
 bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'mechanical/carbentra_smart_switch_animation.blend'),compress=True)
assert hashlib.sha256(MODEL.read_bytes()).hexdigest()==sha
(ROOT/'mechanical/verification/presentation_render_report.json').write_text(json.dumps({'source_blend_sha256':sha,'source_unchanged':True,'renderer':'Cycles '+s.cycles.device,'samples':12,'threads':2,'stills':9,'six_orthographic_views':6,'unique_animation_states':37,'planned_video_resolution':[1280,1280],'qualification':'Real geometric assembly; functional/mains safety qualification pending'},indent=2))
print('PRESENTATION_RENDER_READY',flush=True)
