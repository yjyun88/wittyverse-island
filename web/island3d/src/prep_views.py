# 샘플 2-1 준비: 제미나이 회전 그림을 같은 크기·위치로 맞추고 깊이 지도를 만든다.
# 사용: <transformers 가 있는 파이썬> prep_views.py <views 폴더> <출력 폴더> 0 30 90 ...
import sys, os, numpy as np, torch
from PIL import Image, ImageFilter
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
src, out, angles = sys.argv[1], sys.argv[2], [int(a) for a in sys.argv[3:]]
os.makedirs(out, exist_ok=True)
W, H = 1600, 1000
BG = np.array([6, 27, 61], np.float32)                      # #061b3d
mid = 'depth-anything/Depth-Anything-V2-Small-hf'
proc = AutoImageProcessor.from_pretrained(mid); model = AutoModelForDepthEstimation.from_pretrained(mid).eval()

for ang in angles:
    im = np.asarray(Image.open(os.path.join(src, 'view_%03d.png' % ang)).convert('RGB')).astype(np.float32)
    border = np.concatenate([im[:8].reshape(-1, 3), im[-8:].reshape(-1, 3), im[:, :8].reshape(-1, 3), im[:, -8:].reshape(-1, 3)])
    bg0 = np.median(border, 0)
    dist = np.sqrt(((im - bg0) ** 2).sum(2))
    alpha = np.clip((dist - 10) / 38, 0, 1)
    m = dist > 45
    cols = np.where(m.sum(0) > 10)[0]; rows = np.where(m.sum(1) > 10)[0]
    x0, x1, y0, y1 = cols[0], cols[-1], rows[0], rows[-1]
    s = 0.6 * W / (x1 - x0)
    if (y1 - y0) * s > 0.9 * H: s = 0.9 * H / (y1 - y0)
    cx = (x0 + x1) / 2
    # 배경을 정확한 색으로 다시 합성한 뒤 크기·위치 맞춤
    rgb = im * alpha[..., None] + BG * (1 - alpha[..., None])
    big = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    nw, nh = round(im.shape[1] * s), round(im.shape[0] * s)
    big = big.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new('RGB', (W, H), tuple(int(v) for v in BG))
    ox, oy = round(W / 2 - cx * s), round(0.95 * H - y1 * s)
    canvas.paste(big, (ox, oy))
    canvas.save(os.path.join(out, 'v_%03d.jpg' % ang), quality=86)
    # 깊이
    inp = proc(images=canvas, return_tensors='pt', size={'height': 812, 'width': 1302}, keep_aspect_ratio=True)
    with torch.no_grad(): d = model(**inp).predicted_depth
    d = torch.nn.functional.interpolate(d[None], size=(H // 2, W // 2), mode='bicubic', align_corners=False)[0, 0].numpy()
    d = (d - d.min()) / (d.max() - d.min())
    dm = Image.fromarray((d * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(2.5))
    dm.save(os.path.join(out, 'd_%03d.png' % ang))
    print(ang, '배율 %.2f' % s, '섬 폭', x1 - x0, '깊이 평균 %.2f' % float(d.mean()))
