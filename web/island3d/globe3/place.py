import sys,json,math,numpy as np
from PIL import Image
g=sys.argv[1]
tex=np.array(Image.open(g+'/tex.png')).astype(np.float32)/255
L,Hh,Ac=tex[...,0],tex[...,2],tex[...,3]; HN,WN=L.shape
meta=json.load(open(g+'/props/meta.json'))
WATER={'p10.png','p11.png'}
def px(lat,lon):
    c=int(((lon+180)/360*WN))%WN; r=int(min(HN-1,max(0,(90-lat)/180*HN))); return r,c
def ok(m,lat,lon):
    r,c=px(lat,lon)
    if m['file'] in WATER: return L[r,c]<0.03 and 0.25<Ac[r,c]<0.75
    return L[r,c]>0.97 and Hh[r,c]>0.72
def ang(a,b):
    la1,lo1,la2,lo2=map(math.radians,(a[0],a[1],b[0],b[1]))
    return math.acos(max(-1,min(1,math.sin(la1)*math.sin(la2)+math.cos(la1)*math.cos(la2)*math.cos(lo1-lo2))))
placed=[];R0=586.0
for i,m in enumerate(meta):
    th=math.radians(m['theta'])
    lat0=max(-45,min(45,math.degrees(math.asin(math.cos(th)))/0.82))
    lon0=((m['theta']*2.0+180)%360)-180
    best=None
    for rad in range(0,60):
        for k in range(max(1,rad*6)):
            a=2*math.pi*k/max(1,rad*6)
            lat=lat0+rad*math.sin(a); lon=((lon0+rad*math.cos(a)/max(0.3,math.cos(math.radians(lat)))+180)%360)-180
            if abs(lat)>52 or not ok(m,lat,lon): continue
            sep=all(ang((lat,lon),(p['lat'],p['lon']))>((m['w']+p['w'])/2/R0)*0.85 for p in placed)
            if sep: best=(lat,lon); break
        if best: break
    if not best: print('skip',m['file']); continue
    r,c=px(*best)
    placed.append({**m,'lat':round(best[0],2),'lon':round(best[1],2),'H':round(float(Hh[r,c]),3),'water':m['file'] in WATER})
json.dump(placed,open(g+'/props/placed.json','w'),indent=0)
print(len(placed)); [print(p['file'],p['lat'],p['lon'],p['H']) for p in placed]
