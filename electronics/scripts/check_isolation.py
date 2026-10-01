#!/usr/bin/python3
"""Conservative all-layer XY separation of live/cold copper. No certification claim."""
from pathlib import Path
import pcbnew as p,json,math
R=Path(__file__).resolve().parents[1];b=p.LoadBoard(str(R/'power.kicad_pcb'))
def mm(v):return p.ToMM(v)
def xy(v):return(mm(v.x),mm(v.y))
objs=[]
def add(ref,domain,edges,radius=0,rect=None):
 pts=[v for e in edges for v in e];bounds=(min(x for x,y in pts)-radius,min(y for x,y in pts)-radius,max(x for x,y in pts)+radius,max(y for x,y in pts)+radius);objs.append(dict(ref=ref,domain=domain,edges=edges,r=radius,rect=rect,bounds=bounds))
for f in b.GetFootprints():
 for d in f.Pads():
  n=d.GetNetname();domain='cold'if n.startswith('C_')else'hot'
  if not n:
   if f.GetReference()=='U3':domain='cold'if int(d.GetNumber())<=8 else'hot'
   elif f.GetReference()!='U2':continue
  bb=d.GetBoundingBox();x1,y1,x2,y2=map(mm,[bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()]);v=[(x1,y1),(x2,y1),(x2,y2),(x1,y2)];add(f.GetReference()+'.'+d.GetNumber()+':'+(n or'NC'),domain,list(zip(v,v[1:]+v[:1])),rect=(x1,y1,x2,y2))
for t in b.GetTracks():
 n=t.GetNetname();domain='cold'if n.startswith('C_')else'hot'
 if isinstance(t,p.PCB_VIA):a=xy(t.GetPosition());add('via:'+n,domain,[(a,a)],mm(t.GetWidth(p.F_Cu))/2)
 else:add('track:'+n,domain,[(xy(t.GetStart()),xy(t.GetEnd()))],mm(t.GetWidth())/2)
def ps(q,a,z):
 dx=z[0]-a[0];dy=z[1]-a[1];den=dx*dx+dy*dy;t=max(0,min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/(den or 1)));return math.hypot(q[0]-a[0]-t*dx,q[1]-a[1]-t*dy)
def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def sd(a,b,c,d):
 if orient(a,b,c)*orient(a,b,d)<0 and orient(c,d,a)*orient(c,d,b)<0:return 0
 return min(ps(a,c,d),ps(b,c,d),ps(c,a,b),ps(d,a,b))
def rd(a,b):return math.hypot(max(a[0]-b[2],b[0]-a[2],0),max(a[1]-b[3],b[1]-a[3],0))
minimum=(float('inf'),None,None);close=[];tested=0
hot=[o for o in objs if o['domain']=='hot'];cold=[o for o in objs if o['domain']=='cold']
for a in hot:
 for z in cold:
  lb=rd(a['bounds'],z['bounds'])
  if lb>min(9,minimum[0]):continue
  tested+=1;dist=min(sd(*aa,*zz)for aa in a['edges']for zz in z['edges'])-a['r']-z['r']
  if dist<minimum[0]:minimum=(dist,a['ref'],z['ref'])
  if dist<8-1e-5:close.append(dict(distance_mm=round(dist,6),hot=a['ref'],cold=z['ref']))
report={'board':'power','method':'All copper layers projected into XY; pad bounding rectangles conservatively enclose pad copper; track/via capsules. NC barrier pins assigned to their physical side. No 3D solid-insulation certification.','target_mm':8,'minimum_conservative_mm':round(minimum[0],6),'nearest_pair':list(minimum[1:]),'violations':close,'candidate_pairs_tested':tested,'hot_objects':len(hot),'cold_objects':len(cold)}
(R/'verification'/'isolation_xy.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));assert not close
