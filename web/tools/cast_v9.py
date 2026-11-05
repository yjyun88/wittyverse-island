"""Character sprites for the detail screens: Gemini's layers (shared canvas) -> cropped, scaled WEBP + pivots."""
import base64, io
import numpy as np, cv2
from PIL import Image

def _uri(im):
    b = io.BytesIO(); im.save(b, 'WEBP', quality=90); return 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()

def _largest(im):                                    # drop stray bits (Gemini's arm layer carries a hair bead)
    a = np.asarray(im)[..., 3]; n, lab, st, _ = cv2.connectedComponentsWithStats((a > 20).astype(np.uint8))
    if n <= 2: return im
    keep = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA]); m = cv2.dilate((lab == keep).astype(np.uint8), np.ones((5, 5), np.uint8))
    out = np.asarray(im).copy(); out[..., 3] = out[..., 3] * m; return Image.fromarray(out)

def winni_fix(d, ims):
    """Gemini's cut left the right hair bead on the arm layer (it waved with the hand) and only half of it on the head.
    Move the bead to the head (copied from the finished picture), and drop the thin slivers left on the body under the sleeve."""
    body, arm, head = [np.asarray(im).copy() for im in ims]
    full = np.asarray(Image.open(f'{d}/winni_wave.png').convert('RGBA'))
    arm[:670, :1395, 3] = 0                                         # everything left of the hand / above the sleeve
    y0, y1, x0, x1 = 552, 660, 1312, 1398                           # bead box (source px)
    reg = full[y0:y1, x0:x1].astype(np.float32); hd = head[y0:y1, x0:x1].astype(np.float32); a = reg[..., 3:] / 255
    head[y0:y1, x0:x1] = (reg * a + hd * (1 - a)).astype(np.uint8); head[y0:y1, x0:x1, 3] = np.maximum(hd[..., 3], reg[..., 3]).astype(np.uint8)
    sub = body[700:1000, 1180:1500, 3]; op = cv2.morphologyEx((sub > 40).astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    body[700:1000, 1180:1500, 3] = sub * cv2.dilate(op, np.ones((3, 3), np.uint8))
    # armpit: the sleeve's shoulder end, swept over the whole wave range, painted onto the body under the arm,
    # so the joint stays covered while the arm turns (CSS angles -9.5..+2.5 deg = PIL +9.5..-2.5)
    arm_im, P = Image.fromarray(arm), (1150, 905)
    yy, xx = np.mgrid[:arm.shape[0], :arm.shape[1]]; near = (np.hypot(xx - P[0], yy - P[1]) < 95).astype(np.float32)
    near = cv2.GaussianBlur(near, (0, 0), 6)
    patch = np.zeros_like(arm)
    for ang in np.linspace(-2.5, 9.5, 9):
        r = np.asarray(arm_im.rotate(ang, center=P, resample=Image.BICUBIC)).copy(); r[..., 3] = (r[..., 3] * near).astype(np.uint8)
        pi = Image.fromarray(patch); pi.alpha_composite(Image.fromarray(r)); patch = np.asarray(pi)
    b = Image.fromarray(body); b.alpha_composite(Image.fromarray(patch)); body = np.asarray(b)
    return [Image.fromarray(x) for x in (body, arm, head)]

def pero_fix(d, ims):
    """Split Pero's face into eyes and mouth so a blink closes only the eyes (the whole face used to squash)."""
    eyes, mouth = np.asarray(ims[3]).copy(), np.asarray(ims[4]).copy()
    eyes[700:, :, 3] = 0; mouth[:700, :, 3] = 0
    return ims[:3] + [Image.fromarray(eyes), Image.fromarray(mouth)]

def pack(d, layers, fig_h, fix=None):
    """layers: [(file, pivot or None, clean)] in draw order; returns {w, h, layers: [{uri, piv}]} at fig_h px tall."""
    ims = [Image.open(f'{d}/layers/{f}').convert('RGBA') for f, _, _ in layers]
    ims = [_largest(im) if cl else im for im, (_, _, cl) in zip(ims, layers)]
    if fix: ims = fix(d, ims)
    bb = [im.getbbox() for im in ims]; x0, y0 = min(b[0] for b in bb), min(b[1] for b in bb); x1, y1 = max(b[2] for b in bb), max(b[3] for b in bb)
    k = fig_h / (y1 - y0); W, H = round((x1 - x0) * k), fig_h
    out = []
    for im, (f, piv, _) in zip(ims, layers):
        c = im.crop((x0, y0, x1, y1)).resize((W, H), Image.LANCZOS)
        out.append({'uri': _uri(c), 'piv': [(piv[0] - x0) / (x1 - x0), (piv[1] - y0) / (y1 - y0)] if piv else [.5, .5]})
    return {'w': W, 'h': H, 'layers': out}

def cast(d):
    return {'winni': pack(d, [('winni_body.png', None, False), ('winni_arm.png', (1150, 905), True), ('winni_head.png', (980, 955), False)], 620, winni_fix),
            'pero': pack(d, [('pero_arm_r.png', (1040, 935), False), ('pero_arm_l.png', (545, 900), False), ('pero_body.png', None, False), ('pero_face.png', (800, 620), False), ('pero_face.png', (800, 712), False)], 360, pero_fix)}
