"""Mechanical rendering of the electronics-owned dimensional contract.
Executed inside build_switch.py. Actual circuit/board CAD is in electronics/.
"""
contract=json.loads((ROOT/'electronics/mechanical_interface.json').read_text());bodies=[];board_objects={};coordinates={}
for bd in contract['boards']:
 cn='05_Power_PCB' if bd['name']=='power' else '03_Control_PCB';w=bd['width'];h=bd['height'];z=bd['z_top']
 board=plate(bd['name'].title()+' PCB | actual envelope',w,h,2,bd['z_bottom'],z,PCB,cn);board_objects[bd['name']]=board
 # Authoritative edge notches around the installer screw channels.
 if bd['name']=='power':
  for xx in [-34,34]:cut(board,box('edge notch',(17,9,5),(xx,0,z),None,'Studio',0))
 else:
  for xx in [-30,30]:cut(board,cylinder('screw sleeve clearance',4.25,5,(xx,0,z),None,'Studio'))
 # Four low-stress support bosses, separate from the installer screw channels.
 supports=[(-w/2+3,-h/2+5),(w/2-3,-h/2+5),(-w/2+3,h/2-5),(w/2-3,h/2-5)] if bd['name']=='power' else [(-w/2+5,-h/2+5),(w/2-5,-h/2+5)]
 for xx,yy in supports:
  if bd['name']=='power':
   cylinder('PCB support boss',2.3,6.4,(xx,yy,-28.8),BACK,'06_Backbox')
  else:cylinder('Cold PCB standoff',1.75,1.4,(xx,yy,2.5),WHITE,'04_Isolation_Partition')
 for p in bd['components']:
  ref=p['ref'];x=p['center'][0]-w/2;y=h/2-p['center'][1];dx,dy,dz=p['body'];side=p.get('side','F');z=(bd['z_bottom']-dz) if side=='B' else bd['z_top'];loc=(x,y,z+dz/2);coordinates[ref]=(x,y,z+dz)
  material=BLUE if ref=='J1' else (WHITE if ref in ['J2','J3','F1'] else BLACK)
  obj=box(ref+' | '+p['part'],(dx,dy,dz),loc,material,cn,.14)
  obj['source_contract']='electronics/mechanical_interface.json';obj['simplification']='Vendor body envelope; cosmetic detail simplified, not vendor STEP'
  bodies.append({'ref':ref,'board':bd['name'],'body':p['body'],'center_xyz':loc,'min':[x-dx/2,y-dy/2,z],'max':[x+dx/2,y+dy/2,z+dz]})
  if ref=='RV1':
   bpy.data.objects.remove(obj,do_unlink=True)
   obj=cylinder(ref+' | thermally protected MOV envelope',dx/2,dy,(x,y,z+dz-dx/2),RED,cn);obj.rotation_euler.x=math.pi/2
   for px in [-3.75,3.75]:cylinder(ref+' lead',.45,dz-dx,(x+px,y,z+(dz-dx)/2),STEEL,cn)
  elif ref in ['C15','C16']:
   bpy.data.objects.remove(obj,do_unlink=True);obj=cylinder(ref+' | capacitor maximum envelope',dx/2,dz,loc,BLACK,cn)
   cylinder(ref+' aluminum end',dx/2-.2,.08,(x,y,z+dz-.02 if side=='F' else z+.02),STEEL,cn)
  elif ref in ['J2','J3']:
   # Actual mated connector/cable envelope is coordinated separately.
   obj['isolation']='Cold-side only; not a mains header'
  elif ref.startswith('K'):

   label(ref+' marking',ref+'  G5Q',(x,y,z+dz+.02),2.0,cn)
   for px in [-7.5,7.5]:
    for py in [-3.2,3.2]:box(ref+' solder pin',(1,1,2.3),(x+px,y+py,z-.8),STEEL,cn,0)
  elif ref=='PS1':
   label('PSU marking','RECOM',(x,y+4,z+dz+.02),3,cn);label('PSU secondary marking','5 V / 5 W',(x,y-1,z+dz+.02),2,cn)
  elif ref=='U1':
   # Antenna region remains unshielded; no fake metal over antenna.
   obj.dimensions.z=.8*S;obj.location.z=(z+.4)*S
   sh=box('Radio shield appearance',(12,10.2,1.8),(x,y-2.7,z+1.5),STEEL,cn,.1)
   label('Radio shield marking','ESP32-C3',(x,y-2.7,z+dz+.015),1.65,cn,BLACK)
   for py in [5.3,6.6]:box('Antenna trace visualization',(5,.35,.07),(x,y+py,z+.84),GOLD,cn,0)
  elif ref=='J1':
   for i in range(5):
    xx=x+(i-2)*5.08;cylinder('Terminal captive screw',1.45,.4,(xx,y,z+dz+.2),STEEL,cn);box('Terminal screw slot',(1.75,.23,.10),(xx,y,z+dz+.42),DARK,cn,0)
    aperture=cylinder('Terminal wire-entry opening',1.4,4,(xx,34.5,z+4),None,'Studio');aperture.rotation_euler.x=math.pi/2;cut(back,aperture)
   label('Mains terminal legend','L    N   L1   L2   L3',(x,y+dy/2+1,z+.03),1.3,cn)
  elif ref.startswith('SW'):
   obj.dimensions.z=(dz-.3)*S;obj.location.z=(z+(dz-.3)/2)*S
   cylinder(ref+' actuator',.55,.3,(x,y,z+dz-.15),DARK,cn)
 # Board legend deliberately does not claim certification or rated load.
 label(bd['name']+' PCB legend',('SW3 POWER / MAINS' if bd['name']=='power' else 'SW3 CONTROL / ISOLATED'),(0,-h/2+2,bd['z_top']+.02),1.65,cn)
# Display real routed front/back tracks, derived from current native KiCad files.
# This shallow mask-color relief is visual only; native ECAD remains the copper source.
import re
trace_mat=mat('Actual routed trace paths under green solder mask',(.045,.19,.145),.42)
trace_counts={}
for bd in contract['boards']:
 cn='05_Power_PCB' if bd['name']=='power' else '03_Control_PCB';src=(ROOT/'electronics'/f"{bd['name']}.kicad_pcb").read_text()
 pat=r'\(segment\s*\(start ([\d.eE+\-]+) ([\d.eE+\-]+)\)\s*\(end ([\d.eE+\-]+) ([\d.eE+\-]+)\)\s*\(width ([\d.eE+\-]+)\)\s*\(layer "([^"]+)"\)'
 for layer in ['F.Cu','B.Cu']:
  vs=[];fs=[];z=bd['z_top']+.015 if layer=='F.Cu' else bd['z_bottom']-.015
  for a,b,c,d,width,lay in re.findall(pat,src):
   if lay!=layer:continue
   x0=float(a)-bd['width']/2;y0=bd['height']/2-float(b);x1=float(c)-bd['width']/2;y1=bd['height']/2-float(d);ww=float(width);ll=math.hypot(x1-x0,y1-y0)
   if ll<1e-7:continue
   nx=-(y1-y0)/ll*ww/2;ny=(x1-x0)/ll*ww/2;k=len(vs)
   vs += [(x*S,y*S,z*S) for x,y in [(x0+nx,y0+ny),(x1+nx,y1+ny),(x1-nx,y1-ny),(x0-nx,y0-ny)]];fs.append((k,k+1,k+2,k+3))
  me=bpy.data.meshes.new(bd['name']+' actual '+layer+' trace paths');me.from_pydata(vs,[],fs);me.update();ob=bpy.data.objects.new(me.name,me);C[cn].objects.link(ob);me.materials.append(trace_mat);trace_counts[bd['name']+'_'+layer]=len(fs)
# Pass-through metal screw channels are separated from mains space by modeled polymer.
for x in [-30,30]:
 tube=cylinder('Insulated mounting screw channel OD8',4,32,(x,0,-16),WHITE,'06_Backbox');cut(tube,cylinder('Mount screw bore',2.75,40,(x,0,-16),None,'Studio'))
 for ob in [partition,carrier]:cut(ob,cylinder('Mount service access',4.25,20,(x,0,3),None,'Studio'))
 cylinder('Mounting screw head',2.55,1.2,(x,0,2.5),STEEL,'07_Fasteners');cylinder('Mounting screw shaft concept',1.7,28,(x,0,-12),STEEL,'07_Fasteners');box('Mount screw slot',(3.1,.6,.2),(x,0,3.16),DARK,'07_Fasteners',0)
# Align support openings with actual tact packages, not arbitrary decorative positions.
for ref in ['SW1','SW2','SW3']:
 x,y,z=coordinates[ref];cut(carrier,box('Tact operating aperture',(4.5,4,4),(x,y,5.8),None,'Studio',0))
 cylinder(ref+' molded rocker pusher',1.1,7.2-z,(x,y,(7.2+z)/2),WHITE,'01_Rockers')
# Control module requires clear vertical space through its support carrier.
x,y,z=coordinates['U1'];cut(carrier,box('RF module upper aperture',(16,19,4),(x,y,5.8),None,'Studio',0))
# Actual eight-pin PH connectors and mating reserves from the ECAD contract.
# J3 is on the bottom of the control board; the partition has an isolated-cold cup.
power_bd=next(b for b in contract['boards'] if b['name']=='power')
ctrl_bd=next(b for b in contract['boards'] if b['name']=='control')
j2=next(p for p in power_bd['components'] if p['ref']=='J2')
j3=next(p for p in ctrl_bd['components'] if p['ref']=='J3')
x3=j3['center'][0]-38;y3=38-j3['center'][1]
x2=j2['center'][0]-34;y2=32-j2['center'][1]
cut(partition,box('Cold header pocket opening',(22,9,5),(x3,y3,.9),None,'Studio',0))
pocket=shell('J3 isolated-cold protective pocket',24,11,1.0,22,9,.5,-10.8,-8.8,1.8,WHITE,'04_Isolation_Partition');pocket.location.x=x3*S;pocket.location.y=y3*S
# Explicit 10 mm combined mated height, not just the 6 mm naked header.
box('J3 mated cold harness plug',(20,7,4),(x3,y3,-4.8),DARK,'03_Control_PCB',.16)
box('J2 mated cold harness plug',(7,20,4),(x2,y2,-16),DARK,'05_Power_PCB',.16)
for i in range(8):
 x=x3-7+i*2
 # Individual sealed penetrations preserve a guard surface below the cold connector.
 hole=cylinder('Insulated wire passage',.43,4,(x,y3,-9.8),None,'Studio');cut(pocket,hole)
 cu=bpy.data.curves.new('Isolated harness wire','CURVE');cu.dimensions='3D';cu.bevel_depth=.40*S;cu.bevel_resolution=3
 sp=cu.splines.new('BEZIER');sp.bezier_points.add(3)
 for pt,co in zip(sp.bezier_points,[(x,y3,-6.8),(x,y3,-12.0),(x2-3,y2-7+i*2,-12.0),(x2,y2-7+i*2,-14.0)]):
  pt.co=tuple(v*S for v in co);pt.handle_left_type='AUTO';pt.handle_right_type='AUTO'
 ob=bpy.data.objects.new('Cold eight-wire harness '+str(i+1),cu);C['05_Power_PCB'].objects.link(ob);cu.materials.append(DARK)
# Wire routes are assembly-volume illustrations, not a released harness bending drawing.
# Mechanical readout is recorded before any presentation transformations.
checks=[]
for p in bodies:
 x0,y0,z0=p['min'];x1,y1,z1=p['max']
 if p['board']=='power':fits=(x0>=-35 and x1<=35 and y0>=-33 and y1<=33 and z0>=-32 and z1<=0)
 else:fits=(x0>=-40.3 and x1<=40.3 and y0>=-40.3 and y1<=40.3 and z0>=(-8.8 if p['ref']=='J3' else 1.8) and z1<=7.2)
 checks.append({**p,'fits_nominal_cavity':fits})
pairs=[]
for a,b in itertools.combinations(bodies,2):
 if min(min(a['max'][j],b['max'][j])-max(a['min'][j],b['min'][j]) for j in range(3))>.02:pairs.append([a['ref'],b['ref']])
report={'proposed_exterior_mm':[86,86,43.8],'front_projection_mm':9.8,'rear_projection_mm':34,'backbox_outer_mm':[74,70,34],'backbox_clear_xy_mm':[70,66],'board_contract':'electronics/mechanical_interface.json','board_contract_sha256':__import__('hashlib').sha256((ROOT/'electronics/mechanical_interface.json').read_bytes()).hexdigest(),'actual_kicad_displayed_track_segments':trace_counts,'component_checks':checks,'body_envelope_overlaps':pairs,'nominal_gaps_mm':{'PSU_to_barrier':2.2,'MOV_to_barrier':2.0,'control_PCB_to_barrier':1.4,'radio_body_to_rocker':.6,'C15_C16_to_rear_floor':.6,'J3_mated_to_pocket_floor':2.0},'cold_header_pocket_mm':{'center_xy':[x3,y3],'outer_xy':[24,11],'z_min':-10.8,'floor_top':-8.8},'harness':{'pins':8,'mated_height_budget_mm':10,'required_bend_radius_mm':5,'illustration_only':'Detailed cable routing/bend-radius qualification pending'},'scope':'Nominal package gross fit only; no electrical safety, RF, molding tolerance or thermal qualification','warnings':['Power and control board exact routing is electronics-owned; this is a package-envelope model.','Mounting screw isolation depends on verified polymer properties and insulation path.','Wall cavity and wire-bending space must be measured before installation.','No original product identity or manufacturer dimensional claim.']}
report['displayed_copper_source_sha256']={b['name']:__import__('hashlib').sha256((ROOT/'electronics'/f"{b['name']}.kicad_pcb").read_bytes()).hexdigest() for b in contract['boards']}
(OUT/'verification/dimension_fit_report.json').write_text(json.dumps(report,indent=2));assert all(p['fits_nominal_cavity'] for p in checks),report;assert not pairs,pairs
