import sys, numpy as np, torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
src, out = sys.argv[1], sys.argv[2]
mid = 'depth-anything/Depth-Anything-V2-Small-hf'
proc = AutoImageProcessor.from_pretrained(mid); model = AutoModelForDepthEstimation.from_pretrained(mid).eval()
im = Image.open(src).convert('RGB')
inp = proc(images=im, return_tensors='pt', size={'height': 812, 'width': 1302}, keep_aspect_ratio=True)
with torch.no_grad(): d = model(**inp).predicted_depth
d = torch.nn.functional.interpolate(d[None], size=(im.height, im.width), mode='bicubic', align_corners=False)[0, 0].numpy()
d = (d - d.min()) / (d.max() - d.min())
Image.fromarray((d * 65535).astype(np.uint16)).save(out + '_16.png')
Image.fromarray((d * 255).astype(np.uint8)).save(out + '.png')
print('ok', d.shape, float(d.mean()))
