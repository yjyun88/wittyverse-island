import sys,json,os,numpy as np
from PIL import Image
from scipy import ndimage as nd
src,od=sys.argv[1],sys.argv[2]; os.makedirs(od,exist_ok=True)
im=np.array(Image.open(src).convert('RGBA')).astype(np.float32)
CX,CY,R0=719.4,719.5,586.0
r0,r1=0.985,1.40
NA=int(2*np.pi*R0*1.0); NR=int((r1-r0)*R0)
th=(np.arange(NA)+.5)/NA*2*np.pi          # 0 = 위쪽, 시계방향
rad=r1-(np.arange(NR)+.5)/NR*(r1-r0)      # 위(바깥) -> 아래(지면)
TH,RA=np.meshgrid(th,rad)
px=CX+RA*R0*np.sin(TH); py=CY-RA*R0*np.cos(TH)
strip=np.dstack([nd.map_coordinates(im[...,c],[py,px],order=1,mode='constant') for c in range(4)])
# 지면 바로 위 몇 줄은 지구 표면 자체이므로 알파 판단에서 제외
occ=(strip[:-6,:,3]>60).sum(0)
cols=occ>2
Image.fromarray(strip.clip(0,255).astype(np.uint8)).save(od+'/_strip.png')
runs=[];i=0
while i<NA:
    if cols[i]:
        j=i
        while j<NA and cols[j]: j+=1
        runs.append([i,j]); i=j
    else: i+=1
if len(runs)>1 and runs[0][0]==0 and runs[-1][1]==NA:  # 0도 경계 이어붙임
    runs[0][0]=runs[-1][0]-NA; runs.pop()
print('runs',len(runs),[r[1]-r[0] for r in runs])
json.dump(runs,open(od+'/_runs.json','w'))
