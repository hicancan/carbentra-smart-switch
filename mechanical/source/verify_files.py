#!/usr/bin/env python3
"""Minimal reopen check, physical scale, STL closed-surface edges and media contract."""
from pathlib import Path
import json,struct,collections,hashlib,re,math
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];M=ROOT/'mechanical';model=M/'carbentra_smart_switch.blend'
bpy.ops.wm.open_mainfile(filepath=str(model));s=bpy.context.scene
parts=[o for c in bpy.data.collections if c.name!='Studio' for o in c.objects if o.type=='MESH'];pts=[o.matrix_world@Vector(v) for o in parts for v in o.bound_box]
size=[round((max(v[i] for v in pts)-min(v[i] for v in pts))*1000,3) for i in range(3)]
assert abs(size[0]-86)<.1 and abs(size[1]-86)<.1 and abs(size[2]-43.8)<.1,size
# Verify the visible copper polygons against the final native PCB files.
# Non-rendered via edits do not require rerendering unchanged surface segments.
contract=json.loads((ROOT/'electronics/mechanical_interface.json').read_text());copper_checks={}
pattern=r'\(segment\s*\(start ([\d.eE+\-]+) ([\d.eE+\-]+)\)\s*\(end ([\d.eE+\-]+) ([\d.eE+\-]+)\)\s*\(width ([\d.eE+\-]+)\)\s*\(layer "([^"]+)"\)'
for bd in contract['boards']:
 src=ROOT/'electronics'/f"{bd['name']}.kicad_pcb";matches=re.findall(pattern,src.read_text());layers={}
 for layer in ['F.Cu','B.Cu']:
  expected=[];z=bd['z_top']+.015 if layer=='F.Cu' else bd['z_bottom']-.015
  for a,b,c,d,width,lay in matches:
   if lay!=layer:continue
   x0=float(a)-bd['width']/2;y0=bd['height']/2-float(b);x1=float(c)-bd['width']/2;y1=bd['height']/2-float(d);ll=math.hypot(x1-x0,y1-y0)
   if ll<1e-7:continue
   nx=-(y1-y0)/ll*float(width)/2;ny=(x1-x0)/ll*float(width)/2
   expected.extend([(x*.001,y*.001,z*.001) for x,y in [(x0+nx,y0+ny),(x1+nx,y1+ny),(x1-nx,y1-ny),(x0-nx,y0-ny)]])
  ob=bpy.data.objects[f"{bd['name']} actual {layer} trace paths"];assert len(ob.data.vertices)==len(expected)
  error=max((abs(v.co[j]-p[j]) for v,p in zip(ob.data.vertices,expected) for j in range(3)),default=0);assert error<1e-8,(bd['name'],layer,error)
  layers[layer]={'segments':len(expected)//4,'max_vertex_error_m':error,'matches_final_native_board':True}
 copper_checks[bd['name']]={'final_native_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'layers':layers}
reports=[]
for f in sorted((M/'exports').glob('*.stl')):
 data=f.read_bytes();n=struct.unpack_from('<I',data,80)[0];assert len(data)==84+50*n
 points=[];edges=collections.Counter()
 for i in range(n):
  v=struct.unpack_from('<12f',data,84+i*50)[3:];tri=[tuple(round(z,4) for z in v[j:j+3]) for j in [0,3,6]];points+=tri
  for j in range(3):edges[tuple(sorted((tri[j],tri[(j+1)%3])))]+=1
 closed=all(x==2 for x in edges.values());reports.append({'file':f.name,'triangles':n,'binary_readable':True,'closed_triangle_edges':closed,'bbox_size_mm':[round(max(p[j] for p in points)-min(p[j] for p in points),3) for j in range(3)]})
 assert n>0 and closed,(f.name,n,closed)
raw=(M/'exports/carbentra_smart_switch.glb').read_bytes();assert raw[:4]==b'glTF';assert struct.unpack_from('<I',raw,8)[0]==len(raw)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(M/'exports/carbentra_smart_switch.glb'))
glb_meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert glb_meshes
glb_pts=[o.matrix_world@Vector(v) for o in glb_meshes for v in o.bound_box]
glb_size=[round((max(v[i] for v in glb_pts)-min(v[i] for v in glb_pts))*1000,3) for i in range(3)];assert glb_size==size,glb_size
anim=M/'carbentra_smart_switch_animation.blend';animation={}
if anim.exists():
 bpy.ops.wm.open_mainfile(filepath=str(anim));s=bpy.context.scene;assert(s.frame_start,s.frame_end,s.render.fps)==(1,144,24);s.frame_set(1);locations={o.name:tuple(o.location) for o in bpy.data.objects if o.type=='MESH'};s.frame_set(144);error=max(abs(o.location[i]-locations[o.name][i]) for o in bpy.data.objects if o.name in locations for i in range(3));assert error<1e-8;animation={'reopened':True,'frame_count':144,'fps':24,'endpoint_max_position_error_m':error}
report={'blend_reopened':True,'mesh_objects':len(parts),'overall_bbox_mm':size,'displayed_copper_matches_final_native_boards':copper_checks,'gltf_valid_header_and_size':True,'gltf_reimported':True,'gltf_bbox_mm':glb_size,'stls':reports,'animation':animation,'verification_scope':'File open, exact nominal envelope, final-board displayed track geometry, closed STL edge count and gross package fit only. Not a certification or production validation.'}
(M/'verification/file_open_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
