import json,sys
p=sys.argv[1] if len(sys.argv)>1 else 'data/sample_500.jsonl'
n=0
for n,line in enumerate(open(p,encoding='utf8'),1): json.loads(line)
print(f'VALID JSONL: {n} lines')
