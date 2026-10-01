#!/usr/bin/python3
"""Cross-check actual native ECAD nodes, routing, and physical domain assignments."""
from pathlib import Path
import pcbnew as p,json,math
from sexpr_util import parse,ch
R=Path(__file__).resolve().parents[1];checks={}
for name in ['power','control']:
 b=p.LoadBoard(str(R/(name+'.kicad_pcb')));t=parse((R/'verification'/(name+'.net')).read_text());pairs={};nc=[]
 for net in ch(t,'nets')[1:]:
  nm=json.loads(ch(net,'name')[1])
  for v in net:
   if isinstance(v,list)and v[0]=='node':
    key=(json.loads(ch(v,'ref')[1]),json.loads(ch(v,'pin')[1]))
    if nm.startswith('unconnected-'):nc.append(key)
    else:pairs[key]=nm
 actual={(f.GetReference(),d.GetNumber()):d.GetNetname()for f in b.GetFootprints()for d in f.Pads()if d.GetNetname()}
 expected={k:v for k,v in pairs.items()if not k[0].startswith('#')}
 mismatch=[(k,v,actual.get(k))for k,v in expected.items()if actual.get(k)!=v]+[(k,v,'unexpected')for k,v in actual.items()if k not in expected]+[(k,'NC',actual[k])for k in nc if k in actual]
 drc=json.loads((R/'verification'/(name+'-drc.json')).read_text());erc=json.loads((R/'verification'/(name+'-erc.json')).read_text())
 ercitems=[v for s in erc['sheets']for v in s['violations']]
 checks[name]={'connected_nets':len(set(actual.values())),'connected_pad_nodes':len(actual),'intentional_NC_pins':len(nc),'schematic_pcb_net_mismatches':mismatch,'erc_violations':len(ercitems),'drc_violations':len(drc['violations']),'unconnected_items':len(drc['unconnected_items']),'tracks':sum(not isinstance(t,p.PCB_VIA)for t in b.GetTracks()),'vias':sum(isinstance(t,p.PCB_VIA)for t in b.GetTracks()),'copper_layers':b.GetCopperLayerCount()}
 assert not mismatch,mismatch
 assert not ercitems,ercitems
 assert not drc['violations']and not drc['unconnected_items'],checks[name]
 print(name,checks[name])
# The eight-pin board link is cold on both boards, same net per pin.
j={}
for x in json.loads((R/'manifest.json').read_text())['parts']:
 if x['ref']in['J2','J3']:j[x['ref']]=x['nets']
assert j['J2']==j['J3']and len(j['J2'])==8 and all(n.startswith('C_')for n in j['J2'].values())
checks['cold_harness']={'pins':8,'pinmap_matches':True,'no_hot_net':True}
checks['scope']={'energized':False,'hardware_safety_qualified':False,'load_rating_qualified':False,'RF_tested':False,'energy_calibrated':False,'notes':'ERC/DRC connectivity checks are not mains safety certification; actual hardware remains unenergized.'}
(R/'verification'/'validation.json').write_text(json.dumps(checks,indent=2))
