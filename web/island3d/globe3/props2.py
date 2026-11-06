import sys,json,numpy as np
from PIL import Image
od=sys.argv[1]
s=np.array(Image.open(od+'/_strip.png')).astype(np.float32)
NR,NA=s.shape[:2]; GROUND=236
a=s[:GROUND-10,:,3]
occ=(a>110).sum(0)
cols=occ>1
runs=[];i=0
while i<NA:
    if cols[i]:
        j=i
        while j<NA and cols[j]: j+=1
        runs.append([i,j]); i=j
    else: i+=1
# 가까운 구간 병합(꽃 등), 너무 작은 건 버림
m=[]
for r in runs:
    if m and r[0]-m[-1][1]<4: m[-1][1]=r[1]
    else: m.append(r)
m=[r for r in m if r[1]-r[0]>=10]
# 넓은 구간은 낮은 열에서 분할
out=[]
for a0,a1 in m:
    stack=[(a0,a1)]
    while stack:
        x0,x1=stack.pop()
        if x1-x0<=170: out.append((x0,x1)); continue
        seg=occ[x0+50:x1-50]; c=x0+50+int(np.argmin(seg)); stack+= [(x0,c),(c,x1)]
out.sort()
meta=[]
for n,(x0,x1) in enumerate(out):
    x0p,x1p=max(0,x0-3),min(NA,x1+3)
    crop=s[:GROUND,x0p:x1p]
    rows=np.nonzero((crop[...,3]>20).any(1))[0]; top=max(0,rows.min()-2)
    crop=crop[top:]
    Image.fromarray(crop.clip(0,255).astype(np.uint8)).save(f'{od}/p{n:02d}.png')
    meta.append({'file':f'p{n:02d}.png','theta':float((x0p+x1p)/2/NA*360),'w':int(x1p-x0p),'h':int(crop.shape[0])})
json.dump(meta,open(od+'/meta.json','w'),indent=0)
print(len(meta));[print(x) for x in meta]
# 콘택트 시트
W=sum(x['w']+8 for x in meta);H=max(x['h'] for x in meta)
sheet=Image.new('RGBA',(W,H+20),(50,50,50,255));xx=0
for x in meta:
    p=Image.open(od+'/'+x['file']);sheet.alpha_composite(p,(xx,H-x['h']));xx+=x['w']+8
sheet.convert('RGB').save(od+'/_sheet.png')
