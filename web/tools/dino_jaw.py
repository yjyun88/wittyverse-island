# AR 존 상세 그림(detail_ar.png)의 네온 공룡 아래턱을 떼어 낸다(밤에 입을 움직이는 효과용).
#   bg: 아래턱 네온을 지우고 메운 배경, fg: 아래턱 네온(+주변 빛)만 남긴 RGBA. 좌표는 원본 그림 px.
import numpy as np, cv2
from PIL import Image

BOX = (1622, 732, 1698, 800)                     # 잘라 낼 영역(입을 벌려도 이 안에 들어옴)
PIVOT = (1642, 751)                              # 턱관절(입꼬리와 목 연결부 사이)
BEND = (1643, 1652)                              # 이 x 구간에서 회전이 0→전부로 늘어남(뒤쪽은 붙어 있고 앞쪽만 벌어짐)
JAW = [(1640, 741), (1686, 749), (1690, 782), (1642, 782), (1641, 769), (1638, 761)]   # 아래턱 영역(윗턱·목선 제외)

def jaw(path):
    im = np.asarray(Image.open(path).convert('RGB'))
    x0, y0, x1, y1 = BOX; c = im[y0:y1, x0:x1].copy()
    poly = np.zeros(c.shape[:2], np.uint8); cv2.fillPoly(poly, [np.array([(x - x0, y - y0) for x, y in JAW], np.int32)], 255)
    R, G = c[..., 0].astype(int), c[..., 1].astype(int)
    line = ((R > 200) & (G > 140)).astype(np.uint8) * 255 & poly           # 네온 선
    core = cv2.dilate(line, np.ones((3, 3), np.uint8), iterations=2)       # 선 + 바로 옆 어두운 테
    hole = cv2.dilate(core, np.ones((3, 3), np.uint8), iterations=2)
    bg = cv2.inpaint(c, hole, 6, cv2.INPAINT_TELEA)
    sm = cv2.GaussianBlur(bg, (0, 0), 2.2); w = cv2.GaussianBlur(hole.astype(np.float32) / 255, (0, 0), 1.5)[..., None]
    bg = (bg * (1 - w) + sm * w).astype(np.uint8)                          # 메운 자리의 얼룩을 부드럽게
    a = cv2.GaussianBlur(core.astype(np.float32), (0, 0), 1.2); a = np.clip(a / 255 * 1.4, 0, 1)
    fg = np.dstack([c, (a * 255).astype(np.uint8)])
    return Image.fromarray(bg), Image.fromarray(fg, 'RGBA')

if __name__ == '__main__':
    import sys
    bg, fg = jaw(sys.argv[1]); bg.save(sys.argv[2] + '/jaw_bg.png'); fg.save(sys.argv[2] + '/jaw_fg.png')
