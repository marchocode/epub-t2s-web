#!/usr/bin/env python3
"""
将繁体中文 EPUB 转换为简体中文 EPUB。

策略:
- 解压 EPUB；
- 对所有文本类文件 (xhtml/html/opf/ncx/css) 做繁体->简体转换，
  但只转换 XML/HTML 的文本节点以及特定元数据字段，
  绝不动标签名、属性值、文件名、id、class、href 等，
  以免破坏 EPUB 结构；
- 更新元数据 (dc:title 等转为简体，dc:language 改为 zh-CN)；
- 重新打包为 epub (mimetype 必须第一个且不压缩)。

用法:
    python3 convert_epub.py 输入.epub [输出.epub]
"""

import os
import re
import sys
import shutil
import zipfile
import tempfile
from xml.etree import ElementTree as ET

try:
    from opencc import OpenCC
except ImportError:
    sys.exit("缺少依赖，请先运行: pip3 install opencc-python-reimplemented")

# 繁体 -> 简体 (OpenCC 配置)
cc = OpenCC("t2s")

# 需要转换文本内容的扩展名
TEXT_EXTS = {".xhtml", ".html", ".htm", ".opf", ".ncx", ".xml", ".css"}

# XML 中不应被当作普通文本处理的标签 (其内容为脚本/样式等)
SKIP_TAGS = {"script", "style"}


def convert_text(text: str) -> str:
    return cc.convert(text)


def convert_xml_file(path: str) -> None:
    """按文本节点转换一个 XML/HTML 文件，保留原有结构。"""
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()

    # 用正则定位注释并临时占位，避免 ET 注释处理差异导致结构变化；
    # 直接借助 ET 会丢失 DOCTYPE/注释/xml 声明，所以采用“只替换标签以外的文本”方式。
    #
    # 方案: 用正则在标签之间切分，仅对标签之外的部分做转换。
    # 这样 CDATA 之外的所有文本都会转换，标签/属性完全不受影响。
    parts = re.split(r"(<[^>]*>)", data)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:  # 奇数下标 = 标签本身，原样保留
            out.append(part)
        else:  # 偶数下标 = 文本节点，转换
            out.append(convert_text(part))
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(out))


def update_metadata(opf_path: str) -> None:
    """更新 OPF 中的语言标记为简体中文。"""
    with open(opf_path, "r", encoding="utf-8") as f:
        data = f.read()
    # 语言改为 zh-CN
    data = re.sub(r"(<dc:language[^>]*>)[^<]*(</dc:language>)",
                  r"\1zh-CN\2", data)
    with open(opf_path, "w", encoding="utf-8") as f:
        f.write(data)


def repackage(src_dir: str, out_epub: str) -> None:
    """把目录重新打包成符合规范的 EPUB。"""
    out_epub = os.path.abspath(out_epub)
    if os.path.exists(out_epub):
        os.remove(out_epub)

    mime_path = os.path.join(src_dir, "mimetype")

    with zipfile.ZipFile(out_epub, "w") as zf:
        # mimetype 必须是第一个条目且不压缩
        zf.write(mime_path, "mimetype", compress_type=zipfile.ZIP_STORED)

        for root, dirs, files in os.walk(src_dir):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, src_dir)
                if rel == "mimetype":
                    continue
                zf.write(full, rel, compress_type=zipfile.ZIP_DEFLATED)


def convert_epub(in_epub: str, out_epub: str) -> int:
    """将 in_epub 转换为简体并写出到 out_epub，返回转换的文本文件数。"""
    if not os.path.isfile(in_epub):
        raise FileNotFoundError(f"找不到输入文件: {in_epub}")

    workdir = tempfile.mkdtemp(prefix="epub_conv_")
    try:
        with zipfile.ZipFile(in_epub) as zf:
            zf.extractall(workdir)

        converted = 0
        for root, _dirs, files in os.walk(workdir):
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext in TEXT_EXTS:
                    path = os.path.join(root, name)
                    if ext in (".opf",):
                        update_metadata(path)
                    convert_xml_file(path)
                    converted += 1

        # 确保 mimetype 存在
        mime = os.path.join(workdir, "mimetype")
        if not os.path.exists(mime):
            with open(mime, "w") as f:
                f.write("application/epub+zip")

        repackage(workdir, out_epub)
        return converted
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    in_epub = sys.argv[1]
    if len(sys.argv) >= 3:
        out_epub = sys.argv[2]
    else:
        base, ext = os.path.splitext(in_epub)
        out_epub = base + "_简体" + ext

    if not os.path.isfile(in_epub):
        sys.exit(f"找不到输入文件: {in_epub}")

    print(f"转换 {in_epub} -> {out_epub} ...")
    converted = convert_epub(in_epub, out_epub)
    print(f"已转换 {converted} 个文本文件")
    print("完成 ✅")


if __name__ == "__main__":
    main()
