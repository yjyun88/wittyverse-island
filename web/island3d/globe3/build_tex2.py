# 설계한 대륙 3~4개로 equirect 텍스처 생성 (R=육지, G=연두 무늬, B=높이, A=바다 쪽 해안 근접도)
# 채널 의미·높이·해안 처리는 build_tex.py와 같음. 땅 모양만 원본 역투영 대신 직접 설계.
import sys,numpy as np
from PIL import Image
from scipy import ndimage as nd
out=sys.argv[1]; seed=int(sys.argv[2]) if len(sys.argv)>2 else 7
rng=np.random.default_rng(seed)
W,Hn=2048,1024; w,h=1024,512
u=(np.arange(w)+.5)/w; v=(np.arange(h)+.5)/h
LON,LAT=np.meshgrid((u*2-1)*np.pi,(0.5-v)*np.pi)
P=np.stack([np.cos(LAT)*np.cos(LON),np.cos(LAT)*np.sin(LON),np.sin(LAT)],-1).astype(np.float32)
def vec(lat,lon):
    la,lo=np.radians(lat),np.radians(lon); return np.array([np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)],np.float32)
def bump(lat,lon,deg):
    s=np.radians(deg); d=P@vec(lat,lon); return np.exp((d-1)/(s*s/2))
# 대륙: (중심 위도, 경도, 반경°) 덩어리 묶음. 서로 다른 실루엣이 되게 배치
CONT=[
 [(18,-150,22),(30,-128,16),(4,-138,14),(-10,-155,11)],              # 넓은 북쪽 대륙
 [(-14,-62,20),(-30,-48,15),(2,-72,13),(-22,-80,10)],               # 남쪽 대륙
 [(22,10,20),(10,30,16),(34,-6,12),(-2,14,11)],                     # 가로로 긴 대륙
 [(-12,112,21),(6,128,14),(-28,98,12),(-24,132,10)],                # 남동 대륙
]
ISL=[(46,-90,6),(-44,-10,5),(40,70,6),(-40,170,5),(14,-100,5),(-4,70,6)]
f=np.zeros(LAT.shape,np.float32)
for c in CONT:
    for la,lo,r in c: f=np.maximum(f,bump(la,lo,r*1.4))
for la,lo,r in ISL: f=np.maximum(f,bump(la,lo,r)*0.9)
# 대륙별 개성: 반도(가는 덩어리 사슬)와 만(덩어리 빼기)
def chain(pts,r0,r1,n=24):  # 점을 따라 굵기가 줄어드는 매끄러운 띠
    g=np.zeros(LAT.shape,np.float32); pts=np.array(pts,float)
    seg=np.linspace(0,len(pts)-1,n)
    for t in seg:
        i=min(int(t),len(pts)-2); a=t-i; la,lo=pts[i]*(1-a)+pts[i+1]*a
        g=np.maximum(g,bump(la,lo,r0+(r1-r0)*t/(len(pts)-1)))
    return g
for pts,r0,r1 in [([(-2,-132),(-13,-126),(-22,-118),(-28,-111)],11,7),
                  ([(-36,-46),(-45,-38),(-50,-27)],11,7),
                  ([(30,36),(39,46),(43,58),(42,68)],12,7.5),
                  ([(-2,140),(8,148),(12,157)],12,8)]:
    f=np.maximum(f,chain(pts,r0,r1))
for la,lo,r,a in [(47,-150,8,1.0),(-4,100,9,1.0),(2,24,7,0.9),(-38,-70,7,0.9)]:
    f=f-bump(la,lo,r)*a
# 해안선 굴곡: 중간 크기 무작위 덩어리 합(완만한 노이즈)
def noise(n,deg):
    z=np.zeros(LAT.shape,np.float32)
    for _ in range(n):
        p=rng.normal(size=3); p/=np.linalg.norm(p)
        s=np.radians(deg); z+=rng.uniform(-1,1)*np.exp((P@p.astype(np.float32)-1)/(s*s/2))
    return z
nz=noise(160,10)*0.15+noise(300,4.5)*0.055
f=f+nz
up=lambda a: nd.zoom(a,2,order=3,mode='grid-wrap')
F=up(f); LATf=np.repeat(np.repeat(LAT,2,0),2,1)
land=F>0.40
# 작은 조각 정리: 너무 작은 섬 제거, 작은 호수 메움
lab,n=nd.label(land); s=nd.sum(land,lab,range(1,n+1))
land=np.isin(lab,1+np.where(s>=1500)[0])
lab,n=nd.label(~land); s=nd.sum(~land,lab,range(1,n+1))
land=land|np.isin(lab,1+np.where(s<3000)[0])
def sdf(m):  # 가로 방향은 이어지게(경도 감싸기)
    t=np.concatenate([m,m,m],1)
    d=nd.distance_transform_edt(~t)-nd.distance_transform_edt(t)
    return d[:,W:2*W]
sL=sdf(land)
sL=nd.gaussian_filter(sL,3.0,mode=('nearest','wrap'))
L=np.clip(0.5-sL/1.3,0,1)
# 연두 무늬: 해안에서 떨어진 내륙에 덩어리 무늬
pn=up(noise(240,6.5))
big=(lambda lab,n:np.isin(lab,1+np.where(nd.sum(land,lab,range(1,n+1))>=20000)[0]))(*nd.label(land))
pt=(pn>0.12)&(sL<-22)&big
sT=sdf(pt); sT=nd.gaussian_filter(sT,3.0,mode=('nearest','wrap'))
T=np.clip(0.5-sT/1.6,0,1)*L
BEV=18.0
Hh=np.sin(np.clip(-sL/BEV,0,1)*np.pi/2)
Hh=nd.gaussian_filter(Hh,1.0,mode=('nearest','wrap'))
dist=sdf(L>=0.5).clip(0,None)
A=np.clip(1-dist/16,0,1)*(1-L)
Image.fromarray((np.dstack([L,T,Hh,A]).clip(0,1)*255).astype(np.uint8),'RGBA').save(out)
lab,n=nd.label(L>0.5); s=sorted(nd.sum(L>0.5,lab,range(1,n+1)).astype(int))[::-1]
print('land',round(float((L>0.5).mean()),3),'pieces',n,s[:8])
prev=np.zeros((Hn,W,3),np.uint8); prev[...]=(70,140,200)
prev[L>0.5]=(120,170,80); prev[(T>0.5)]=(170,200,90)
Image.fromarray(prev).resize((1024,512)).save(out.replace('.png','_preview.png'))
