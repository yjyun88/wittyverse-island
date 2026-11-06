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
def noise(n,deg):
    z=np.zeros(LAT.shape,np.float32)
    for _ in range(n):
        p=rng.normal(size=3); p/=np.linalg.norm(p)
        s=np.radians(deg); z+=rng.uniform(-1,1)*np.exp((P@p.astype(np.float32)-1)/(s*s/2))
    return z
# 대륙: 길쭉하게 휜 타원 하나씩. (위도, 경도, 긴 반경°, 짧은 반경°, 기울기°, 휨)
CONT=[(24,-142,40,21,-20,0.9),(-18,-66,34,17,100,-0.8),(22,30,38,16,6,0.7),(-14,120,36,20,-40,-0.6)]
wx=noise(120,16)*0.10; wy=noise(120,16)*0.10   # 큰 규모 비틀기
f=np.full(LAT.shape,-1.0,np.float32); gs=[]
for la,lo,A_,B_,th,bend in CONT:
    c=vec(la,lo); e=np.cross([0,0,1],c); e/=np.linalg.norm(e); nn=np.cross(c,e)
    pc=P@c; x=np.arctan2(P@e,pc); y=np.arctan2(P@nn,pc)
    x=x+wx; y=y+wy
    t=np.radians(th); xr=x*np.cos(t)+y*np.sin(t); yr=-x*np.sin(t)+y*np.cos(t)
    xr=xr/np.radians(A_*1.4); yr=yr/np.radians(B_*1.85)-bend*xr*xr*0.5
    g=np.where(pc>0,1-np.sqrt(xr*xr+yr*yr),-1)
    gs.append(g)
gs=np.sort(np.stack(gs),0); g1,g2=gs[-1],gs[-2]
f=np.minimum(g1,(g1-g2)*1.2-0.22)   # 두 대륙이 맞닿는 곳엔 해협
# 섬: 작은 휜 타원(위도, 경도, 긴 반경°, 짧은 반경°, 기울기°, 휨) + 잔굴곡
def ell(la,lo,A_,B_,th,bend,warp=0.0):
    c=vec(la,lo); e=np.cross([0,0,1],c); e/=np.linalg.norm(e); nn=np.cross(c,e)
    pc=P@c; x=np.arctan2(P@e,pc)+warp*wx; y=np.arctan2(P@nn,pc)+warp*wy
    t=np.radians(th); xr=x*np.cos(t)+y*np.sin(t); yr=-x*np.sin(t)+y*np.cos(t)
    xr=xr/np.radians(A_); yr=yr/np.radians(B_)-bend*xr*xr*0.5
    return np.where(pc>0,1-np.sqrt(xr*xr+yr*yr),-1)
# 곁가지 없이 덩어리 하나. 길이:폭은 1.2~1.5로 넓적하게
# 섬: 방향마다 반지름이 다른 불규칙 다각형형(곶과 만이 여러 개, 항상 한 덩어리)
# (위도, 경도, 반경°, 가로세로비, 기울기°, 모양 시드)
ISL=[(-45,8,8.5,1.6,15,1),                                    # 큰 섬
     (52,-87,5.2,1.5,25,2),(51,99,5.0,1.35,-30,3),            # 중간 섬
     ]
def rough(la,lo,R,asp,th,sd):
    r2=np.random.default_rng(1000+sd)
    c=vec(la,lo); e=np.cross([0,0,1],c); e/=np.linalg.norm(e); nn=np.cross(c,e)
    pc=P@c; x=np.degrees(np.arctan2(P@e,pc)); y=np.degrees(np.arctan2(P@nn,pc))
    t=np.radians(th); xr=(x*np.cos(t)+y*np.sin(t))/asp; yr=-x*np.sin(t)+y*np.cos(t)
    rho=np.hypot(xr,yr); ang=np.arctan2(yr,xr)
    k=np.ones_like(rho)
    for m in range(2,9):
        amp=r2.uniform(0.2,1.0)*0.34/m*(0.5 if m==2 else 1.0)   # 2차(콩 모양) 성분은 약하게
        k=k+amp*np.cos(m*ang+r2.uniform(0,2*np.pi))
    k=np.maximum(k,0.55)
    return np.where(pc>0,1-rho/(R*k),-1)
f=f+noise(90,12)*0.17
# 작은 섬: 크기·위치 무작위. 대륙 해안과 다른 섬에서 충분히 떨어진 곳만
ri=np.random.default_rng(int(sys.argv[3]) if len(sys.argv)>3 else 11)
contd=nd.distance_transform_edt(np.concatenate([f<=0]*3,1))[:,w:2*w]*(180/h)   # 대륙까지 거리(°)
def gdist(a,b):
    la1,lo1,la2,lo2=map(np.radians,(a[0],a[1],b[0],b[1]))
    return np.degrees(np.arccos(np.clip(np.sin(la1)*np.sin(la2)+np.cos(la1)*np.cos(la2)*np.cos(lo1-lo2),-1,1)))
small=[]
SIZES=[5.0,4.4,3.8,3.4,3.0,2.7,2.5,2.3,2.2,2.2]     # 크기 차등(큰 것부터 자리 잡기)
for R in SIZES:
  for _ in range(4000):
    la=np.degrees(np.arcsin(ri.uniform(-0.82,0.82))); lo=ri.uniform(-180,180)
    rr=int((90-la)/180*h); cc=int((lo+180)/360*w)%w
    if contd[rr,cc] < R*1.6+3: continue
    if any(gdist((la,lo),(p[0],p[1])) < (R+p[2])*1.6+4 for p in ISL+small): continue
    small.append((la,lo,R,float(ri.uniform(1.1,1.8)),float(ri.uniform(0,180)),20+len(small))); break
# 사용자 요청으로 뺀 섬(남태평양 쪽 세 개)
REMOVED=[(-15,-174),(-23,172),(-47,-168),(28,142)]
small=[p for p in small if all(gdist((p[0],p[1]),q)>3 for q in REMOVED)]
print('small',[(round(a),round(b),round(c,1)) for a,b,c,*_ in small])
isl=np.full(LAT.shape,-1.0,np.float32)
for p in ISL+small: isl=np.maximum(isl,rough(*p))
rng=np.random.default_rng(seed+100)   # 섬 잔굴곡은 별도 난수(대륙 모양 유지)
isl=isl+noise(1400,2.6)*0.06
f=np.maximum(f,isl)           # 완만한 해안 굴곡만
f=f+0.40
up=lambda a: nd.zoom(a,2,order=3,mode='grid-wrap')
F=up(f); LATf=np.repeat(np.repeat(LAT,2,0),2,1)
land=F>0.40
# 작은 조각 정리: 너무 작은 섬 제거, 작은 호수 메움
lab,n=nd.label(land); s=nd.sum(land,lab,range(1,n+1))
land=np.isin(lab,1+np.where(s>=350)[0])
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
# 연두빛: 테두리 없는 그라데이션. 내륙 깊이 + 큰 규모의 완만한 변화
pn=up(noise(160,13)); pn=(pn-pn.mean())/(pn.std()+1e-6)
inl=np.clip(-sL/90,0,1)
t=inl*0.55+pn*0.38-0.12
T=np.clip(t/0.75,0,1); T=T*T*(3-2*T)*0.7
T=nd.gaussian_filter(T,10,mode=('nearest','wrap'))*L
BEV=18.0
Hh=np.sin(np.clip(-sL/BEV,0,1)*np.pi/2)
Hh=nd.gaussian_filter(Hh,1.0,mode=('nearest','wrap'))
dist=sdf(L>=0.5).clip(0,None)
A=np.clip(1-dist/16,0,1)*(1-L)
Image.fromarray((np.dstack([L,T,Hh,A]).clip(0,1)*255).astype(np.uint8),'RGBA').save(out)
lab,n=nd.label(L>0.5); s=sorted(nd.sum(L>0.5,lab,range(1,n+1)).astype(int))[::-1]
print('land',round(float((L>0.5).mean()),3),'pieces',n,s[:8])
prev=np.zeros((Hn,W,3),np.uint8); prev[...]=(70,140,200)
prev[L>0.5]=(120,170,80); prev[L>0.5]=(np.array([120,170,80])*(1-T[L>0.5,None])+np.array([190,215,80])*T[L>0.5,None]).astype(np.uint8)
Image.fromarray(prev).resize((1024,512)).save(out.replace('.png','_preview.png'))
