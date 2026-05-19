from PIL import Image, ImageDraw
import os

sizes = [16, 32, 48, 64, 128, 256]
frames = []

for size in sizes:
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景圆形
    margin = int(size * 0.04)
    bg_color = (30, 80, 180)
    shadow_color = (15, 50, 130)

    # 阴影
    draw.ellipse([margin+1, margin+2, size-margin+1, size-margin+2], fill=shadow_color)
    # 主背景圆
    draw.ellipse([margin, margin, size-margin, size-margin], fill=bg_color)
    # 高光
    hl_size = int(size * 0.35)
    draw.ellipse([margin+int(size*0.1), margin+int(size*0.08),
                  margin+hl_size, margin+int(hl_size*0.6)],
                 fill=(80, 140, 230))

    cx = size // 2
    cy = size // 2

    if size >= 48:
        # 画书本
        bw = int(size * 0.52)
        bh = int(size * 0.38)
        bx = cx - bw // 2
        by = cy - int(size * 0.02)

        # 书本阴影
        draw.rectangle([bx+2, by+2, bx+bw+2, by+bh+2], fill=(10, 40, 110))
        # 左页
        draw.rectangle([bx, by, bx+bw//2, by+bh], fill=(255, 255, 255))
        # 右页
        draw.rectangle([bx+bw//2, by, bx+bw, by+bh], fill=(235, 245, 255))
        # 书脊
        spine_w = max(2, int(size * 0.03))
        draw.rectangle([bx+bw//2-spine_w, by-2, bx+bw//2+spine_w, by+bh+2], fill=(200, 160, 60))

        # 页面线条
        line_color = (160, 200, 255)
        line_margin = int(size * 0.07)
        line_gap = int(size * 0.065)
        for i in range(3):
            y_line = by + line_margin + i * line_gap
            if y_line < by + bh - 4:
                draw.rectangle([bx+int(size*0.05), y_line,
                                 bx+bw//2-int(size*0.06), y_line+max(1, int(size*0.025))],
                                fill=line_color)
                draw.rectangle([bx+bw//2+int(size*0.04), y_line,
                                 bx+bw-int(size*0.05), y_line+max(1, int(size*0.025))],
                                fill=line_color)

        # 字母 A 悬浮在书本上方
        letter_size = int(size * 0.28)
        letter_y = by - letter_size - int(size * 0.04)
        letter_x = cx - letter_size // 2

        # A 的金色背景圆
        pad = int(size * 0.04)
        draw.ellipse([letter_x-pad, letter_y-pad,
                      letter_x+letter_size+pad, letter_y+letter_size+pad],
                     fill=(255, 200, 50))

        # 绘制字母 A
        stroke = max(2, int(size * 0.04))
        draw.line([letter_x + letter_size//2, letter_y + stroke,
                   letter_x + stroke, letter_y + letter_size - stroke],
                  fill=(30, 80, 180), width=stroke)
        draw.line([letter_x + letter_size//2, letter_y + stroke,
                   letter_x + letter_size - stroke, letter_y + letter_size - stroke],
                  fill=(30, 80, 180), width=stroke)
        mid_y = letter_y + int(letter_size * 0.55)
        draw.line([letter_x + int(letter_size*0.25), mid_y,
                   letter_x + int(letter_size*0.75), mid_y],
                  fill=(30, 80, 180), width=stroke)

    else:
        # 小尺寸：简单白色 A
        stroke = max(1, size // 10)
        lx, ly = cx - size//5, cy + size//5
        rx, ry = cx + size//5, cy + size//5
        tx, ty = cx, cy - size//4
        draw.line([tx, ty, lx, ly], fill='white', width=stroke)
        draw.line([tx, ty, rx, ry], fill='white', width=stroke)
        mid_y = cy + size//10
        draw.line([cx - size//8, mid_y, cx + size//8, mid_y], fill='white', width=stroke)

    frames.append(img)

# 输出路径与脚本同目录
script_dir = os.path.dirname(os.path.abspath(__file__))
ico_path = os.path.join(script_dir, 'favicon.ico')
png_path = os.path.join(script_dir, 'favicon_preview.png')

# 保存 ICO（多尺寸）
frames[0].save(
    ico_path,
    format='ICO',
    sizes=[(s, s) for s in sizes],
    append_images=frames[1:]
)

# 保存 PNG 预览（256px）
frames[-1].save(png_path)

print(f"favicon.ico -> {ico_path}")
print(f"favicon_preview.png -> {png_path}")