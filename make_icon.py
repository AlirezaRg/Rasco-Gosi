"""
Generates rasco.ico from the digital skull design.
"""
from PIL import Image, ImageDraw
import math

def hex_pts(cx, cy, r, angle_deg=0):
    pts = []
    for i in range(6):
        a = math.radians(60*i + angle_deg)
        pts.append((cx + r*math.cos(a), cy + r*math.sin(a)))
    return pts

def bezier(p0, p1, p2, p3, n=30):
    pts = []
    for i in range(n+1):
        t = i/n
        x = (1-t)**3*p0[0]+3*(1-t)**2*t*p1[0]+3*(1-t)*t**2*p2[0]+t**3*p3[0]
        y = (1-t)**3*p0[1]+3*(1-t)**2*t*p1[1]+3*(1-t)*t**2*p2[1]+t**3*p3[1]
        pts.append((x, y))
    return pts

def alpha(color, a):
    r,g,b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
    return (int(r*a), int(g*a), int(b*a))

def draw_skull(size=256):
    img = Image.new('RGBA', (size, size), (0,0,0,255))
    d = ImageDraw.Draw(img)

    S = size / 256
    cx, cy = size//2, int(size*0.52)

    M = '#00ffe0'
    Mc = (0,255,224)
    D  = (0,50,45)
    MID= (0,180,160)

    def s(v): return int(v*S)
    def p(x,y): return (int(cx+x*S), int(cy+y*S))

    # ── skull shape ──
    skull = (
        bezier(p(-105,10),p(-115,-30),p(-110,-110),p(-70,-148)) +
        bezier(p(-70,-148),p(-35,-183),p(35,-183),p(70,-148)) +
        bezier(p(70,-148),p(110,-110),p(115,-30),p(105,10)) +
        bezier(p(105,10),p(88,52),p(50,66),p(0,70)) +
        bezier(p(0,70),p(-50,66),p(-88,52),p(-105,10))
    )
    d.polygon(skull, fill=(12,12,12,255), outline=alpha(M,0.5))
    # glow rings
    for width_extra, opa in [(6, 0.15),(12, 0.07)]:
        # approximate glow by drawing outline multiple times slightly expanded — skip for simplicity
        pass

    # ── circuit lines ──
    circuits = [
        [p(-20,-168),p(-20,-138),p(-52,-138),p(-52,-118)],
        [p(20,-168),p(20,-138),p(52,-138),p(52,-118)],
        [p(-82,-98),p(-100,-98),p(-100,-68)],
        [p(82,-98),p(100,-98),p(100,-68)],
        [p(0,-178),p(0,-152),p(-26,-152)],
        [p(0,-178),p(0,-152),p(26,-152)],
    ]
    for path in circuits:
        for i in range(len(path)-1):
            d.line([path[i], path[i+1]], fill=alpha(M,0.25), width=max(1,s(1)))
        for pt in path:
            r2 = max(2,s(2))
            d.ellipse([pt[0]-r2,pt[1]-r2,pt[0]+r2,pt[1]+r2], fill=alpha(M,0.5))

    # ── eyes ──
    eye_y_off = -58
    for side in (-1,1):
        ex, ey = cx+s(52*side), cy+s(eye_y_off)

        # hex rings
        for ring_r, opa in [(30,0.2),(22,0.3)]:
            hpts = hex_pts(ex, ey, s(ring_r), 15)
            d.polygon(hpts, outline=alpha(M,opa), fill=None)

        # socket
        d.ellipse([ex-s(23),ey-s(17),ex+s(23),ey+s(17)], fill=(0,0,0,255))

        # glow layers
        for r2, opa in [(20,0.4),(14,0.6),(8,0.8),(4,1.0)]:
            rx, ry = s(r2), int(s(r2)*0.72)
            d.ellipse([ex-rx,ey-ry,ex+rx,ey+ry], fill=D, outline=alpha(M,opa))

        # iris spokes
        for spoke in range(8):
            a = math.radians(45*spoke)
            x1,y1 = ex+s(9)*math.cos(a), ey+s(9)*math.sin(a)*0.7
            x2,y2 = ex+s(15)*math.cos(a), ey+s(15)*math.sin(a)*0.7
            d.line([(x1,y1),(x2,y2)], fill=alpha(M,0.6), width=max(1,s(1)))

        # pupil
        d.ellipse([ex-s(5),ey-s(4),ex+s(5),ey+s(4)], fill=(0,0,0,255), outline=Mc, width=max(1,s(2)))

        # eye brackets
        for bx2,by2,sx2,sy2 in [(-23,-17,1,1),(-23,17,1,-1),(23,-17,-1,1),(23,17,-1,-1)]:
            bpx, bpy = ex+s(bx2), ey+s(by2)
            d.line([(bpx+s(sx2*9),bpy),(bpx,bpy)], fill=alpha(M,0.7), width=max(1,s(1)))
            d.line([(bpx,bpy),(bpx,bpy+s(sy2*7))], fill=alpha(M,0.7), width=max(1,s(1)))

    # ── nose ──
    nose = (
        bezier(p(0,-8),p(-14,4),p(-18,22),p(-8,29)) +
        [(p(0,26)[0],p(0,26)[1])] +
        list(reversed(bezier(p(8,29),p(18,22),p(14,4),p(0,-8))))
    )
    d.polygon(nose, fill=(0,0,0,255), outline=alpha(M,0.2))
    for ns in (-1,1):
        nx,ny = cx+s(6*ns), cy+s(24)
        d.ellipse([nx-s(7),ny-s(5),nx+s(7),ny+s(5)], fill=D, outline=alpha(M,0.5))

    # ── cheekbone plates ──
    for side in (-1,1):
        px2,py2 = cx+s(79*side), cy+s(-5)
        pts2 = [
            (px2-s(5*side),py2-s(14)),
            (px2+s(22*side),py2-s(10)),
            (px2+s(24*side),py2+s(10)),
            (px2-s(5*side),py2+s(14)),
        ]
        d.polygon(pts2, fill=(14,14,14,255), outline=alpha(M,0.4))

    # ── temporal hex implants ──
    for side in (-1,1):
        ix,iy = cx+s(103*side), cy+s(-78)
        hpts2 = hex_pts(ix, iy, s(13))
        d.polygon(hpts2, fill=(8,8,8,255), outline=Mc)
        d.ellipse([ix-s(5),iy-s(5),ix+s(5),iy+s(5)], fill=Mc)

    # ── jaw ──
    jaw = (
        bezier(p(-90,55),p(-90,100),p(-50,128),p(0,136)) +
        bezier(p(0,136),p(50,128),p(90,100),p(90,55))
    )
    d.polygon(jaw, fill=(7,7,7,255), outline=alpha(M,0.2))

    # ── teeth ──
    t_count,t_w,t_gap = 7,13,2
    total_tw = t_count*(t_w+t_gap)-t_gap
    t_y = cy+s(58)
    for i in range(t_count):
        tx = cx - s(total_tw//2) + i*s(t_w+t_gap)
        th = s(13) if (i==0 or i==t_count-1) else s(17)
        d.rectangle([tx,t_y,tx+s(t_w),t_y+th], fill=(200,196,180,255), outline=(100,100,80,255))
        d.rectangle([tx,t_y,tx+s(t_w),t_y+s(3)], fill=(255,255,255,180))

    # ── forehead diamond ──
    dcx, dcy = cx, cy+s(-172)
    sz2 = s(10)
    dpts = [(dcx+sz2*math.cos(math.radians(45+90*i)), dcy+sz2*math.sin(math.radians(45+90*i))) for i in range(4)]
    d.polygon(dpts, fill=(10,10,10,255), outline=Mc)
    d.ellipse([dcx-s(4),dcy-s(4),dcx+s(4),dcy+s(4)], fill=Mc)

    # ── HUD bar ──
    bar_y = cy + s(168)
    d.rectangle([cx-s(70),bar_y-s(11),cx+s(70),bar_y+s(11)], fill=(6,6,6,255), outline=alpha(M,0.4))
    d.ellipse([cx-s(60),bar_y-s(4),cx-s(52),bar_y+s(4)], fill=Mc)

    # ── corner brackets ──
    for x1,y1,sx2,sy2 in [(s(16),s(16),1,1),(size-s(16),s(16),-1,1),(s(16),size-s(16),1,-1),(size-s(16),size-s(16),-1,-1)]:
        d.line([(x1,y1),(x1+sx2*s(20),y1)], fill=alpha(M,0.3), width=max(1,s(1)))
        d.line([(x1,y1),(x1,y1+sy2*s(20))], fill=alpha(M,0.3), width=max(1,s(1)))

    return img

# Generate multiple sizes for .ico
sizes = [256, 128, 64, 48, 32, 16]
images = []
for sz in sizes:
    img = draw_skull(sz)
    images.append(img)

out_path = r"C:\Users\admin\Desktop\koli\Rasco-Gosi\rasco.ico"
images[0].save(
    out_path,
    format='ICO',
    sizes=[(s,s) for s in sizes],
    append_images=images[1:]
)
print(f"Icon saved: {out_path}")
