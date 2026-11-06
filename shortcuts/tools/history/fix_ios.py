import json,pathlib,plistlib,subprocess,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2];DIR=ROOT/'outputs/命运方舟一键助手'
p=json.loads((DIR/'命运方舟一键助手.source.json').read_text())
counts={}
for a in p['WFWorkflowActions']:
 k=a['WFWorkflowActionIdentifier'];v=a['WFWorkflowActionParameters']
 if k.endswith('.conditional') and v.get('WFControlFlowMode')==0:
  x=v['WFInput']
  if x.get('WFSerializationType')=='WFTextTokenAttachment':v['WFInput']={'Type':'Variable','Variable':x};counts['conditional']=counts.get('conditional',0)+1
 if k.endswith('.count') and 'WFInput' in v:v['Input']=v.pop('WFInput');counts['count']=counts.get('count',0)+1
 if k.endswith('.text.match') and 'WFInput' in v:v['text']=v.pop('WFInput');counts['match']=counts.get('match',0)+1
p['WFWorkflowName']='命运方舟一键助手·修正版'
raw=ROOT/'work/shortcuts/unsigned/ios-fixed.shortcut';raw.write_bytes(plistlib.dumps(p,fmt=plistlib.FMT_BINARY))
(DIR/'命运方舟一键助手.source.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
result=DIR/'命运方舟一键助手·修正版.shortcut'
subprocess.run(['/usr/bin/shortcuts','sign','--mode','anyone','--input',str(raw),'--output',str(result)],check=True)
(DIR/'SHA256SUMS.txt').write_text(hashlib.sha256(result.read_bytes()).hexdigest()+'  '+result.name+'\n')
print(counts)
