import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'activity-manifest.json').read_text())
for name in ('server','windows'):
    cfg=json.loads((ROOT/name/'service/activity.json').read_text())
    assert cfg['version']==manifest['version']
    assert sorted(map(int,cfg['verified_claims']))==manifest[name]
workflow=json.loads((ROOT/'shortcuts/source/workflow.json').read_text())
claims=[]
for a in workflow['WFWorkflowActions']:
    p=a['WFWorkflowActionParameters']
    if a['WFWorkflowActionIdentifier'].endswith('.downloadurl') and 'partnergettaskreward' in p.get('WFURL',''):
        assert p['WFURL'].endswith(manifest['version'])
        values={x['WFKey']['Value']['string']:x['WFValue']['Value']['string'] for x in p['WFFormValues']['Value']['WFDictionaryFieldValueItems'] if x['WFKey']['Value']['string'] in ('task_id','type')}
        assert values['type']=='1'
        claims.append(int(values['task_id']))
assert sorted(claims)==manifest['shortcuts']
print('三端活动配置符合清单（保留已注明的 ID 1 差异）。')
