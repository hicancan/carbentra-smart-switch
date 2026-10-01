#!/usr/bin/env python3
"""Parametric 86-format switch concept, native meters; dimensions authored in mm.
Run through scripts/dev.ps1. Uses the electronic layout contract.
"""
from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from local_runtime import runtime, configure_cycles, memory_kib, drawing_font

import sys, math, json, struct, itertools
import bpy, bmesh
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'mechanical'; VIS=ROOT/'presentation'; S=.001
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.length_unit='MILLIMETERS'
s.render.engine='CYCLES';configure_cycles(s);s.cycles.samples=12;s.cycles.use_denoising=True
s.render.threads_mode='FIXED';s.render.threads=2;s.render.resolution_x=1280;s.render.resolution_y=1280;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA';s.render.film_transparent=True
s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.exposure=-.45
bpy.context.preferences.filepaths.temporary_directory=str(runtime());bpy.context.preferences.filepaths.save_version=0
world=bpy.data.worlds.new('Soft studio');s.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.75,.79,.77,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.5
C={}
for n in ['01_Rockers','02_Face_Rim','03_Control_PCB','04_Isolation_Partition','05_Power_PCB','06_Backbox','07_Fasteners','Studio']:
 c=bpy.data.collections.new(n);s.collection.children.link(c);C[n]=c

def into(o,c):
 for old in list(o.users_collection):old.objects.unlink(o)
 C[c].objects.link(o);return o

def mat(n,col,rough=.38,metal=0):
 m=bpy.data.materials.new(n);m.diffuse_color=(*col,1);m.use_nodes=True;p=m.node_tree.nodes['Principled BSDF'];p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;return m
WHITE=mat('Warm porcelain white polymer | material grade TBD',(.82,.84,.835),.27)
BACK=mat('Warm white molded housing | grade unqualified',(.69,.73,.73),.43)
DARK=mat('Recess / dark polymer',(.047,.064,.067),.54)
PCB=mat('Forest green solder mask',(.025,.13,.105),.35)
GOLD=mat('Copper alloy contact appearance',(.61,.40,.10),.3,.72)
STEEL=mat('Fastener metal appearance',(.48,.55,.57),.25,.8)
BLACK=mat('Component epoxy',(.020,.027,.031),.43)
BLUE=mat('Terminal polymer',(.075,.30,.29),.45)
SILK=mat('PCB legend',(.83,.89,.85),.45)
RED=mat('Protective device body',(.55,.14,.10),.55)

def finish(o,n,m,c):
 o.name=n;into(o,c)
 if m:o.data.materials.append(m)
 return o

def bevel(o,w=.16):
 mo=o.modifiers.new('Small manufactured edge relief','BEVEL');mo.width=w*S;mo.segments=3
 mo=o.modifiers.new('Weighted flat normals','WEIGHTED_NORMAL');mo.keep_sharp=True
 return o

def box(n,d,loc,m,c,b=.12):
 bpy.ops.mesh.primitive_cube_add(size=1,location=tuple(v*S for v in loc));o=bpy.context.object;o.dimensions=tuple(v*S for v in d);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);finish(o,n,m,c)
 if b:bevel(o,b)
 return o

def cylinder(n,r,h,loc,m,c):
 bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=r*S,depth=h*S,location=tuple(v*S for v in loc));o=finish(bpy.context.object,n,m,c);bevel(o,.06);return o

def path(w,h,r):
 # Counterclockwise rounded rectangle; independent corners BL,BR,TR,TL.
 if isinstance(r,(int,float)):r=[r]*4
 out=[]
 for (cx,cy,deg,rad) in [(-w/2+r[0],-h/2+r[0],180,r[0]),(w/2-r[1],-h/2+r[1],270,r[1]),(w/2-r[2],h/2-r[2],0,r[2]),(-w/2+r[3],h/2-r[3],90,r[3])]:
  for i in range(13):
   a=math.radians(deg+i*90/12);out.append((cx+rad*math.cos(a),cy+rad*math.sin(a)))
 return out

def extrusion(n,points,z0,z1,m,c,xy=(0,0)):
 vs=[((x+xy[0])*S,(y+xy[1])*S,z*S) for z in [z0,z1] for x,y in points];k=len(points)
 fs=[tuple(range(k-1,-1,-1)),tuple(range(k,2*k))]+[(i,(i+1)%k,(i+1)%k+k,i+k) for i in range(k)]
 me=bpy.data.meshes.new(n);me.from_pydata(vs,[],fs);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
 o=bpy.data.objects.new(n,me);C[c].objects.link(o)
 if m:o.data.materials.append(m)
 return o

def plate(n,w,h,r,z0,z1,m,c,xy=(0,0)):return extrusion(n,path(w,h,r),z0,z1,m,c,xy)
def ring(n,w,h,r,iw,ih,ir,z0,z1,m,c):
 p=path(w,h,r);q=path(iw,ih,ir);k=len(p);vs=[(x*S,y*S,z*S) for z in [z0,z1] for poly in [p,q] for x,y in poly];fs=[]
 for i in range(k):
  j=(i+1)%k
  fs.extend([(i,j,j+2*k,i+2*k),(i+k,i+3*k,j+3*k,j+k),(i,j,i*0+j+k,i+k),(i+2*k,i+3*k,j+3*k,j+2*k)])
 me=bpy.data.meshes.new(n);me.from_pydata(vs,[],fs);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();o=bpy.data.objects.new(n,me);C[c].objects.link(o);o.data.materials.append(m);return o

def shell(n,w,h,r,iw,ih,ir,zb,zf,zt,m,c):
 p=path(w,h,r);q=path(iw,ih,ir);k=len(p)
 vs=[(x*S,y*S,z*S) for poly,z in [(p,zb),(p,zt),(q,zf),(q,zt)] for x,y in poly]
 fs=[tuple(range(k-1,-1,-1)),tuple(range(2*k,3*k))]
 for i in range(k):
  j=(i+1)%k;fs += [(i,j,k+j,k+i),(k+i,k+j,3*k+j,3*k+i),(2*k+i,3*k+i,3*k+j,2*k+j)]
 me=bpy.data.meshes.new(n);me.from_pydata(vs,[],fs);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
 o=bpy.data.objects.new(n,me);C[c].objects.link(o);o.data.materials.append(m);return o

def cut(o,tool):
 mo=o.modifiers.new('Functional opening','BOOLEAN');mo.operation='DIFFERENCE';mo.object=tool;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mo.name);bpy.data.objects.remove(tool,do_unlink=True)

def label(n,t,loc,size,c,matr=SILK):
 cu=bpy.data.curves.new(n,'FONT');cu.body=t;cu.size=size*S;cu.align_x='CENTER';o=bpy.data.objects.new(n,cu);C[c].objects.link(o);o.location=tuple(v*S for v in loc);cu.materials.append(matr);return o

# Front is +Z; wall/mount rear plane is Z=0. No original brand markings.
rockers=[]
for i,x in enumerate([-26.85,0,26.85]):
 radii=[7,.5,.5,7] if i==0 else ([.5,7,7,.5] if i==2 else .5)
 o=plate(f'Rocker {i+1} | 26.3 x 79.4',26.3,79.4,radii,7.2,9.8,WHITE,'01_Rockers',(x,0));bevel(o,.18);rockers.append(o)
 # The clips and actuator are a tooling concept, not life-tested snap fits.
 for y in [-26,26]:
  box(f'Rocker {i+1} retention tab {y}',(3,2,2.5),(x,y,6.05),WHITE,'01_Rockers',.08)
  box(f'Rocker {i+1} retention hook {y}',(3.6,2.6,.35),(x,y,4.825),WHITE,'01_Rockers',.04)
 o['mechanism']='Momentary rocker concept; travel, force, pivot and retention need tool/tolerance validation'
rim=ring('Face rim | 86 x 86',86,86,9,80.6,80.6,7.9,0,7.8,WHITE,'02_Face_Rim');bevel(rim,.25)
# Separate cold-side carrier supports keys without exposing primary electronics.
carrier=plate('Cold-side rocker support carrier',79.8,79.8,7.2,5.1,6.1,BACK,'02_Face_Rim')
for xx in [-26.85,0,26.85]:
 for yy in [-26,26]:cut(carrier,box('Rocker retention slot',(3.3,2.3,4),(xx,yy,5.5),None,'Studio',0))
# Final tactile switch openings are derived from electronics contract below.
# Large central component aperture; the partition underneath closes touch access.
# RF clearance is cut from the final component position below.
back=shell('Recessed backbox | integral 2 mm walls and floor',74,70,5,70,66,3,-34,-32,0,BACK,'06_Backbox')
base=back
# Terminal opening is assigned below from authoritative ECAD contract.
partition=plate('Protective insulating partition | 1.8 nominal',73.5,69.5,4.5,0,1.8,WHITE,'04_Isolation_Partition')
partition['safety']='Solid protective partition plus certified component isolation are required; thickness/material/creepage qualification pending'
# Coordination-specific geometry and real component envelopes live separately.
exec(compile((OUT/'source/internal_layout.py').read_text(),str(OUT/'source/internal_layout.py'),'exec'))

# Union molded tabs and pushers into their actual structural rocker pieces.
for i,ob in enumerate(rockers,1):
 attachments=[x for x in list(C['01_Rockers'].objects) if x!=ob and (x.name.startswith(f'Rocker {i} retention') or x.name.startswith(f'SW{i} molded'))]
 for a in attachments:
  mo=ob.modifiers.new('Integral molded feature','BOOLEAN');mo.operation='UNION';mo.object=a;bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_apply(modifier=mo.name);bpy.data.objects.remove(a,do_unlink=True)
# Union rear support features into the one printable conceptual backbox shell.
for a in list(C['06_Backbox'].objects):
 if a==back:continue
 mo=back.modifiers.new('Integral backbox feature','BOOLEAN');mo.operation='UNION';mo.object=a;bpy.context.view_layer.objects.active=back;bpy.ops.object.modifier_apply(modifier=mo.name);bpy.data.objects.remove(a,do_unlink=True)

# Unify the insulating guard and its cold connector pocket as a single nominal part.
for a in list(C['04_Isolation_Partition'].objects):
 if a==partition or a.type!='MESH':continue
 mo=partition.modifiers.new('Integral protective guard feature','BOOLEAN');mo.operation='UNION';mo.object=a;bpy.context.view_layer.objects.active=partition;bpy.ops.object.modifier_apply(modifier=mo.name);bpy.data.objects.remove(a,do_unlink=True)

for xx in [-30,30]:cut(back,cylinder('Complete installer screw bore',2.75,45,(xx,0,-14),None,'Studio'))

# Weld boolean/bevel zero-area remnants before native and STL delivery.
# 0.0001 mm is far below the nominal concept geometry precision.
for ob in [rim,carrier,partition,back]+rockers:
 bpy.context.view_layer.objects.active=ob
 for mod in list(ob.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
 bm=bmesh.new();bm.from_mesh(ob.data)
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
 bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7)
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free();ob.data.update()

# Studio, camera and bound checks.
def view(loc,target,scale):
 cam.location=Vector(tuple(v*S for v in loc));cam.rotation_euler=(Vector(tuple(v*S for v in target))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale*S
 q=cam.rotation_euler.to_quaternion()
 for o,co,power,size in lightdefs:
  o.location=Vector(tuple(v*S for v in target))+q@Vector(tuple(v*S for v in co));o.rotation_euler=(Vector(tuple(v*S for v in target))-o.location).to_track_quat('-Z','Y').to_euler();o.data.energy=power;o.data.size=size*S
bpy.ops.object.camera_add();cam=finish(bpy.context.object,'Studio camera',None,'Studio');cam.data.type='ORTHO';cam.data.clip_start=.001;cam.data.clip_end=5;s.camera=cam
lightdefs=[]
for n,co,power,size in [('Key softbox',(-80,95,150),1.6,130),('Rim softbox',(90,45,90),.7,100),('Front fill',(10,-70,160),.35,120)]:
 bpy.ops.object.light_add(type='AREA');o=finish(bpy.context.object,n,None,'Studio');lightdefs.append((o,co,power,size))
view((130,-175,180),(0,0,-8),132)
s['design']='CARBENTRA SW3 | proposed three-channel mains light switch'
s['reference_status']='User photographs only; exact manufacturer/model unconfirmed. All mechanical dimensions proposed.'
s['qualification']='Engineering concept. No mains safety, load, metering accuracy, RF, thermal or material certification implied.'
s['nominal_envelope_mm']='86 x 86 face; 43.8 total depth; rear projection 34; front projection 9.8'
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   a.spaces.active.region_3d.view_distance=.16;a.spaces.active.region_3d.view_location=Vector((0,0,-.008));a.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion();a.spaces.active.region_3d.view_perspective='ORTHO';a.spaces.active.shading.color_type='MATERIAL';a.spaces.active.overlay.show_floor=False
bpy.context.view_layer.update()
product=[o for c in C.values() if c.name!='Studio' for o in c.objects]
bpy.ops.object.select_all(action='DESELECT')
for o in product:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'exports/carbentra_smart_switch.glb'),export_format='GLB',use_selection=True,export_apply=True,export_extras=True)
for obs,name in [([rim],'face_rim_mm'),([carrier],'rocker_carrier_mm'),([o for o in C['04_Isolation_Partition'].objects if o.type=='MESH'],'isolation_partition_mm'),([back,base],'backbox_mm')]+[([o],f'rocker_{i+1}_mm') for i,o in enumerate(rockers)]:
 bpy.ops.object.select_all(action='DESELECT')
 for o in obs:o.select_set(True)
 bpy.context.view_layer.objects.active=obs[0];bpy.ops.wm.stl_export(filepath=str(OUT/'exports'/f'{name}.stl'),export_selected_objects=True,global_scale=1000,apply_modifiers=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'carbentra_smart_switch.blend'),compress=True)
print('MODEL_AND_EXPORTS_READY',flush=True)
