def extract_lyrics(text: str) -> str:
    # 1) пытаемся найти fenced-block
    blocks = re.findall(r'```(?:\w*\n)?([\s\S]*?)```', text)
    for blk in blocks:
        if re.search(r'\[(Verse|Chorus|Bridge|Outro|Drop|Intro)', blk):
            return blk.strip()

    # 2) fallback — поиск по меткам
    lines = text.splitlines()
    song_lines = []
    in_song = False
    for line in lines:
        if re.match(r'\[(Verse|Chorus|Bridge|Outro|End|Drop|Intro)', line):
            in_song = True
        if in_song:
            song_lines.append(line)
        if in_song and re.match(r'\[End\]', line):
            break

    return "\n".join(song_lines).strip()