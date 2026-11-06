"""Rebuild a signed shortcut from the canonical, credential-free action graph."""
import argparse
import json
from pathlib import Path
import plistlib
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent

def validate(workflow):
    actions = workflow['WFWorkflowActions']
    ids = [a['WFWorkflowActionParameters']['UUID'] for a in actions]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate action UUID')
    available = set(ids)
    stack = []
    def references(value):
        if isinstance(value, dict):
            if value.get('Type') == 'ActionOutput' and value.get('OutputUUID') not in available:
                raise ValueError('Unresolved output reference')
            for v in value.values(): references(v)
        elif isinstance(value, list):
            for v in value: references(v)
    for action in actions:
        p = action['WFWorkflowActionParameters']
        references(p)
        if 'WFControlFlowMode' in p:
            if p['WFControlFlowMode'] == 0:
                stack.append(p['GroupingIdentifier'])
            elif p['WFControlFlowMode'] == 2:
                if not stack or stack.pop() != p['GroupingIdentifier']:
                    raise ValueError('Unbalanced control flow')
    if stack:
        raise ValueError('Unclosed control flow')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unsigned-only', action='store_true')
    args=parser.parse_args()
    workflow=json.loads((ROOT/'source/workflow.json').read_text(encoding='utf-8'))
    validate(workflow)
    out=ROOT/'build';out.mkdir(exist_ok=True)
    unsigned=out/'workflow.unsigned.shortcut'
    unsigned.write_bytes(plistlib.dumps(workflow,fmt=plistlib.FMT_BINARY))
    if args.unsigned_only:
        print('Generated unsigned action file; not an iPhone-importable signed release.')
        return
    if not shutil.which('shortcuts'):
        raise SystemExit('Signing requires macOS shortcuts CLI. Use --unsigned-only elsewhere.')
    release=ROOT/'releases'/f"{workflow['WFWorkflowName']}.shortcut"
    subprocess.run(['shortcuts','sign','--mode','anyone','--input',str(unsigned),'--output',str(release)],check=True)
    print('Signed release:',release.name)

if __name__=='__main__':main()
