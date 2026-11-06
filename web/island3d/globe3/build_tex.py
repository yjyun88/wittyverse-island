# 원본 정면 지구 그림 -> 3D 구용 equirect 텍스처 (R=육지, G=연두 무늬, B=높이)
import sys,numpy as np
from PIL import Image
from scipy import ndimage as nd
src,out=sys.argv[1],sys.argv[2]
im=np.array(Image.open(src).convert('RGB')).astype(np.float32)
r,g,b=im[...,0],im[...,1],im[...,2]
CX,CY,R0=719.4,719.5,586.0
yy,xx=np.mgrid[0:im.shape[0],0:im.shape[1]]
rr=np.hypot(xx-CX,yy-CY)/R0
land=nd.gaussian_filter(np.clip((g-b+20)/80,0,1),1.0)>0.5
patch=(nd.gaussian_filter(np.clip((r-110)/80,0,1),1.5)>0.5)&land&(rr<0.84)
def sdf(m): return nd.distance_transform_edt(~m)-nd.distance_transform_edt(m)  # +: 바깥
sdL,sdT=sdf(land),sdf(patch)
R=R0*0.94; W,Hn=2048,1024
u=(np.arange(W)+.5)/W; v=(np.arange(Hn)+.5)/Hn
LON,LAT=np.meshgrid((u*2-1)*np.pi,(0.5-v)*np.pi)
k=0.62; latS=LAT*0.82
lonF=np.clip(LON*k,-1.55,1.55)
lonB=np.clip(np.angle(np.exp(1j*(LON-np.pi)))*k,-1.55,1.55)
c=np.cos(LON); wF=np.clip((c+0.5)/1.0,0,1); wF=wF*wF*(3-2*wF); wB=1-wF
def sample(img,lon,lat):
    px=CX+R*np.cos(lat)*np.sin(lon); py=CY-R*np.sin(lat)
    return nd.map_coordinates(img,[py,px],order=1,mode='nearest')
def blend(f): return wF*sample(f,lonF,latS)+wB*sample(f,lonB,-latS)
sL=blend(sdL); sT=blend(sdT)
# 극지방은 대륙이 자연스럽게 바다로 끝나도록 거리장에 바다 쪽 가중
polar=np.clip((np.abs(np.degrees(LAT))-36)/18,0,1)
sL=sL+polar**1.3*90; sT=sT+polar*50
# 해안선 둥글게: 거리장을 부드럽게 만든 뒤 경계 추출
sL=nd.gaussian_filter(sL,3.0,mode=('nearest','wrap'))
sT=nd.gaussian_filter(sT,3.0,mode=('nearest','wrap'))
# 위도가 높은 곳에 작게 남은 섬 조각은 바다로 지움
latd=np.abs(np.degrees(LAT))
lab,nl=nd.label(sL<0)
for i in range(1,nl+1):
    m=lab==i; area=m.sum()
    if area<4000 and latd[m].mean()>40:
        sL[nd.binary_dilation(m,iterations=6)]=np.maximum(sL[nd.binary_dilation(m,iterations=6)],6.0)
L=np.clip(0.5-sL/1.3,0,1)
T=np.clip(0.5-sT/1.6,0,1)*L
# 육지 단면: 해안에서 둥글게 솟는 베개형(사인 곡선), 폭 BEV 픽셀
BEV=18.0
x=np.clip(-sL/BEV,0,1)
Hh=np.sin(x*np.pi/2)
Hh=nd.gaussian_filter(Hh,1.0,mode=('nearest','wrap'))
# 바다 쪽 해안 근접도(해안 그림자용)
dist=nd.distance_transform_edt(L<0.5)   # 최종 육지 기준(지운 섬 자리에 그림자가 남지 않게)
A=np.clip(1-dist/16,0,1)*(1-L)
Image.fromarray((np.dstack([L,T,Hh,A]).clip(0,1)*255).astype(np.uint8),'RGBA').save(out)
