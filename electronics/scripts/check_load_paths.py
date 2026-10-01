#!/usr/bin/python3
"""Verify main lamp-current paths without using narrow signal-reference branches.
Digital connectivity evidence only; no thermal or current-rating qualification.
"""
from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from local_runtime import runtime, configure_cycles, memory_kib, drawing_font

import pcbnew as p,json
from sexpr_util import parse,ch,ser
E=Path(__file__).resolve().parents[1];R=E.parent
s=parse((E/'power.kicad_pcb').read_text())
# Retain only candidate current trunks and their large vias. Pads remain native.
s=[e for e in s if not(isinstance(e,list) and ((e[0]=='segment' and float(ch(e,'width')[1])<1.1999)or(e[0]=='via'and float(ch(e,'size')[1])<1.5999)))]
tmp=runtime()/'load-path-only.kicad_pcb';tmp.write_text(ser(s)+'\n');b=p.LoadBoard(str(tmp));b.BuildConnectivity();conn=b.GetConnectivity()
pads={(f.GetReference(),d.GetNumber()):d for f in b.GetFootprints()for d in f.Pads()}
def reachable(src,dst):
 a,z=pads[src],pads[dst];todo=[a];seen=set()
 while todo:
  x=todo.pop();uid=x.m_Uuid.AsString()
  if uid in seen:continue
  seen.add(uid)
  if uid==z.m_Uuid.AsString():return True,len(seen)
  todo+=list(conn.GetConnectedTracks(x))+list(conn.GetConnectedPads(x))
 return False,len(seen)
paths=[('line_to_fuse',('J1','1'),('F1','1'),'L_IN'),('fuse_to_shunt',('F1','2'),('R7','1'),'H_GND')]
for i in range(1,4):paths += [(f'shunt_to_relay_{i}',('R7','4'),(f'K{i}','2'),'H_LOAD'),(f'relay_{i}_to_terminal',(f'K{i}','3'),('J1',str(i+2)),f'L_OUT{i}')]
result=[]
for name,a,z,n in paths:
 ok,count=reachable(a,z);result.append(dict(path=name,source='.'.join(a),destination='.'.join(z),net=n,connected_without_signal_tracks=ok,minimum_retained_track_width_mm=1.2,minimum_retained_via_diameter_mm=1.6));print(name,ok,count)
report={'method':'Native KiCad connectivity with every track narrower than 1.2 mm and every via smaller than 1.6 mm removed in a temporary copy. Original pads preserved. Each path must remain connected.','paths':result,'temperature_rise_tested':False,'qualified_load_rating':False,'note':'F1 and shunt internal current paths are component internals, not bridged by PCB copper in this check.'}
(E/'verification'/'load_paths.json').write_text(json.dumps(report,indent=2)+'\n');assert all(x['connected_without_signal_tracks']for x in result)
