import json
import requests
import re
import os
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


def get_headers():
    return {
        'Host': 'music.163.com',
        'Connection': 'keep-alive',
        'Content-Type': "application/x-www-form-urlencoded; charset=UTF-8",
        'Referer': 'http://music.163.com/',
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36"
                      " (KHTML, like Gecko) Chrome/33.0.1750.152 Safari/537.36"
    }


def get_cookies():
    return dict(appver="1.2.1", os="osx")


def show_progress(response):
    content = bytes()
    total_size = response.headers.get('content-length')
    if total_size is None:
        content = response.content
        return content
    else:
        total_size = int(total_size)
        bytes_so_far = 0

        for chunk in response.iter_content():
            content += chunk
            bytes_so_far += len(chunk)
            progress = round(bytes_so_far * 1.0 / total_size * 100)
            print(f"Progress: {progress}%")
        return content


def http_request(method, action, query=None, timeout=1):
    headers = get_headers()
    cookies = get_cookies()
    res = None

    if method == "GET":
        res = requests.get(action, headers=headers, cookies=cookies, timeout=timeout)
    elif method == "POST":
        res = requests.post(action, query, headers=headers, cookies=cookies, timeout=timeout)
    elif method == "POST_UPDATE":
        res = requests.post(action, query, headers=headers, cookies=cookies, timeout=timeout)
        cookies.update(res.cookies.get_dict())
    content = show_progress(res)
    content_str = content.decode('utf-8')
    content_dict = json.loads(content_str)
    return content_dict


def song_detail(nid):
    action = f'http://music.163.com/api/song/detail?ids=%5B{nid}%5D'
    res_data = http_request('GET', action)
    return res_data['songs'][0]


def get_lyric_by_musicid(mid):
    url = f'http://music.163.com/api/song/lyric?id={mid}&lv=1&kv=1&tv=-1'
    return http_request('POST', url)


def clean_lyric(lrc):
    r = []
    is_empty = False
    for line in lrc.strip().split('\n'):
        line = line.strip()
        if not is_empty:
            r.append(line)
            if line == '':
                is_empty = True
        else:
            if line != '':
                r.append(line)
                is_empty = False
    return '\n'.join(r)


def get_song_lrc(uid):
    song = song_detail(uid)
    song_name = song['name'].strip()
    song_img = song["album"]["blurPicUrl"]
    artist_name = song['artists'][0]['name'].strip()

    lrc = get_lyric_by_musicid(uid)
    if 'lrc' in lrc and 'lyric' in lrc['lrc'] and lrc['lrc']['lyric'] != '':
        lrc = lrc['lrc']['lyric']
        pat = re.compile(r'\[.*]')
        lrc = re.sub(pat, "", lrc)
        lrc = lrc.strip()
    else:
        lrc = u'纯音乐，无歌词'
    song_lrc = clean_lyric(lrc)
    return song_name, song_lrc, song_img, artist_name


def detect_language(text):
    # 检测文本中的字符是否包含中文
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    else:
        return 'en'


def select_font(lrc, zh_font='fonts/PingFang Bold.ttf', en_font='fonts/System San Francisco Text Bold.ttf',
                font_size=50):
    # 根据歌词选择字体
    language = detect_language(lrc)
    font_path = zh_font if language == 'zh' else en_font
    return ImageFont.truetype(font_path, font_size)


def wrap_text(text, font, max_width, line_spacing=30, extra_spacing=20):
    lines = []
    words = text.split(' ')
    current_line = ""

    for word in words:
        # 计算加入当前单词后的行宽
        test_line = current_line + ("" if current_line == "" else " ") + word
        bbox = font.getbbox(test_line)
        test_line_width = bbox[2] - bbox[0]

        if test_line_width <= max_width:
            # 如果加入单词后不超宽，则继续添加
            current_line = test_line
        else:
            # 如果超宽，检查是否是单字母的情况
            if len(current_line) > 0 and len(current_line.split(' ')[-1]) == 1:
                # 如果当前行最后一个单词是一个字母，将其移动到下一行
                last_word = current_line.split(' ').pop()
                current_line = " ".join(current_line.split(' ')[:-1])
                lines.append(current_line.strip())
                current_line = last_word + " " + word
            else:
                lines.append(current_line.strip())
                current_line = word

    # 处理最后一行
    if len(current_line) > 0:
        lines.append(current_line.strip())

    return lines


def save_img(name, artist, lrc, img_url, aid, save_dir='output/'):
    font_size = 50  # 设置更大的字体大小
    line_space = 30
    song_name_font_size = 40  # 歌名字体大小
    artist_font_size = 25
    share_img_width = 640
    padding = 50
    song_name_space = 50
    banner_space = 60
    text_color = '#767676'
    banner_size = 20
    icon = 'source/logo_light.jpg'

    lyric_font = select_font(lrc, font_size=font_size)
    song_name_font = select_font(name, font_size=song_name_font_size)
    artist_font = select_font(lrc, font_size=artist_font_size)
    max_width = share_img_width - 2 * padding
    wrapped_lrc = wrap_text(lrc, lyric_font, max_width)
    draw = ImageDraw.Draw(Image.new(mode='RGB', size=(1, 1)))

    # 计算歌词的总高度
    draw = ImageDraw.Draw(Image.new(mode='RGB', size=(1, 1)))
    total_height = 0
    for line in wrapped_lrc:
        bbox = draw.textbbox((0, 0), line, font=lyric_font)
        total_height += bbox[3] - bbox[1] + line_space

    if img_url.startswith('http'):
        raw_img = requests.get(img_url)
        album_img = Image.open(BytesIO(raw_img.content))
    else:
        album_img = Image.open(img_url)

    iw, ih = album_img.size
    album_h = ih * share_img_width // iw

    h = album_h + padding + total_height + banner_space + banner_size + padding + 150

    resized_album = album_img.resize((share_img_width, album_h), resample=3)
    icon_img = Image.open(icon)

    out_img = Image.new(mode='RGB', size=(share_img_width, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(out_img)

    # 添加封面
    out_img.paste(resized_album, (0, 0))

    # 添加歌词
    y_text = album_h + padding
    previous_line_empty = False  # 用于跟踪是否遇到空行
    for line in wrapped_lrc:
        draw.text((padding, y_text), line, font=lyric_font, fill=text_color, spacing=line_space)
        line_height = draw.textbbox((0, 0), line, font=lyric_font, spacing=line_space)[3] - \
                      draw.textbbox((0, 0), line, font=lyric_font, spacing=line_space)[1]
        y_text += line_height + line_space
        if previous_line_empty and line.strip():  # 在空行后且遇到新段落时增加额外间距
            y_text += extra_space
        previous_line_empty = not line.strip()  # 判断当前行是否为空行

    y_song_name = y_text + song_name_space

    # 计算歌名文本的宽度
    bbox = draw.textbbox((0, 0), name, font=lyric_font)
    sw, sh = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 添加歌名和作者名称在左下角
    y_artist_name = h - padding - artist_font_size - banner_size - banner_space + 30  # 作者名的Y轴位置
    draw.text((padding, y_artist_name), artist, font=artist_font, fill=text_color)

    y_song_name = y_artist_name - song_name_font_size - 10  # 歌名的Y轴位置，调整为紧邻作者名之上
    draw.text((padding, y_song_name), name, font=song_name_font, fill=text_color)

    # 添加Apple Music标签
    y_banner = h - padding - banner_size
    out_img.paste(icon_img, (padding, y_banner - 2))

    # 生成二维码
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=0,
    )
    qr.add_data('https://music.apple.com/cn/album/' + aid)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    qr_size = (120, 120)  # 设置你想要的大小
    qr_img = qr_img.resize(qr_size, Image.Resampling.LANCZOS)

    # 确定二维码的位置（放在图片右下角）
    qr_position = (share_img_width - qr_img.size[0] - padding, h - qr_img.size[1] - padding)
    out_img.paste(qr_img, qr_position)

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    img_save_path = os.path.join(save_dir, name + '.png')
    out_img.save(img_save_path)


def main():
    pic_style = int(input('请选择生成模式(1: 输入歌曲链接生成图片 2: 使用本地图片及歌词): '))
    if pic_style == 1:
        nid = int(input('请输入网易云音乐歌曲ID: '))
        aid = str(input('请输入Apple Music ID: '))
        line_range = input('请输入歌词范围: ')
        song_name, song_lrc, song_img, artist = get_song_lrc(nid)
        lrcs = song_lrc.split('\n')
        tmp_lrcs = []
        for i in line_range.split(','):
            if '-' in i:
                a, b = i.split('-')
                tmp_lrcs += lrcs[int(a) - 1:int(b)]
            else:
                tmp_lrcs.append(lrcs[int(i) - 1])
        song_lrc = '\n'.join(tmp_lrcs)
        save_img(song_name, artist, song_lrc, song_img, aid)
    elif pic_style == 2:
        img_file = input('请输入图片路径: ')
        text = str(input('请输入歌词: '))
        name = str(input('请输入歌曲名: '))
        artist = str(input('请输入作者: '))
        aid = input('请输入Apple Music ID: ')
        save_img(name, artist, text, img_file, aid)


if __name__ == '__main__':
    main()
