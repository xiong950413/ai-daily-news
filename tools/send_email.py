#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 日报邮件推送脚本（零第三方依赖，纯 Python 标准库）

用法:
    python3 tools/send_email.py <日报md路径> [日期YYYY-MM-DD]

示例:
    python3 tools/send_email.py docs/2026-10-13.md 2026-10-13

环境变量（必须）:
    SMTP_USER        发件邮箱（QQ 邮箱地址）
    SMTP_AUTH_CODE   SMTP 授权码（QQ 邮箱设置里生成的 16 位授权码，不是 QQ 密码）
    MAIL_TO          收件邮箱（可选，默认同 SMTP_USER）

成功输出 MAIL_SENT，失败输出 MAIL_FAIL 及原因（退出码 1）。
"""
import os
import re
import sys
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465  # SSL


def md_inline(text: str) -> str:
    """行内 Markdown 转换：**粗体**、`代码`、[链接](url)"""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def is_table_sep(line: str) -> bool:
    """判断是否为表格分隔行，如 |---|---|---|"""
    s = line.strip()
    return bool(re.match(r"^\|?[\s:|-]+\|[\s:|-]*$", s)) and "-" in s


def split_row(line: str):
    """拆分表格行为单元格"""
    s = line.strip().strip("|")
    return [c.strip() for c in s.split("|")]


def md_to_html(md_text: str) -> str:
    """针对日报格式（标题/引用/表格/列表/段落）的轻量 Markdown -> HTML 转换"""
    lines = md_text.splitlines()
    html_parts = []
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:  # 空行
            i += 1
            continue

        # 表格：当前行含 | 且下一行是分隔行
        if "|" in stripped and i + 1 < n and is_table_sep(lines[i + 1]):
            header = split_row(stripped)
            i += 2
            rows = []
            while i < n and "|" in lines[i].strip() and lines[i].strip():
                rows.append(split_row(lines[i].strip()))
                i += 1
            thead = "".join(f"<th>{md_inline(c)}</th>" for c in header)
            trs = "".join(
                "<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in row) + "</tr>"
                for row in rows
            )
            html_parts.append(
                "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>"
                % (thead, trs)
            )
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            html_parts.append(f"<h{level}>{md_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # 引用块
        if stripped.startswith(">"):
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            html_parts.append("<blockquote>%s</blockquote>" % md_inline(" ".join(quote)))
            continue

        # 无序列表
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < n and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append("<li>%s</li>" % md_inline(re.sub(r"^[-*]\s+", "", lines[i].strip())))
                i += 1
            html_parts.append("<ul>%s</ul>" % "".join(items))
            continue

        # 有序列表
        if re.match(r"^\d+[.、]\s+", stripped):
            items = []
            while i < n and re.match(r"^\d+[.、]\s+", lines[i].strip()):
                items.append("<li>%s</li>" % md_inline(re.sub(r"^\d+[.、]\s+", "", lines[i].strip())))
                i += 1
            html_parts.append("<ol>%s</ol>" % "".join(items))
            continue

        # 分隔线
        if re.match(r"^-{3,}$", stripped):
            html_parts.append("<hr/>")
            i += 1
            continue

        # 普通段落（合并连续行）
        para = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|>|\||[-*]\s|\d+[.、]\s|-{3,}$)", lines[i].strip()
        ):
            para.append(lines[i].strip())
            i += 1
        html_parts.append("<p>%s</p>" % md_inline(" ".join(para)))

    return "\n".join(html_parts)


def build_email_html(md_text: str) -> str:
    body = md_to_html(md_text)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="margin:0;padding:0;background:#f4f5f7;">
<div style="max-width:860px;margin:0 auto;padding:16px;font-family:'Microsoft YaHei','PingFang SC',Arial,sans-serif;color:#2c3e50;font-size:14px;line-height:1.7;">
<div style="background:#ffffff;border-radius:8px;padding:24px 28px;border:1px solid #e5e7eb;">
{body}
</div>
<div style="text-align:center;color:#9aa3af;font-size:12px;margin-top:12px;">
本邮件由定时任务自动发送 · 仓库：https://gitee.com/helixiong/ai-daily-news
</div>
</div>
</body>
</html>"""


def extract_date(md_path: str, arg_date=None) -> str:
    if arg_date:
        return arg_date
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(md_path))
    if m:
        return m.group(1)
    import datetime
    return datetime.date.today().strftime("%Y-%m-%d")


def main():
    if len(sys.argv) < 2:
        print("MAIL_FAIL: 缺少参数，用法: python3 tools/send_email.py <日报md路径> [日期]")
        sys.exit(1)

    md_path = sys.argv[1]
    if not os.path.isfile(md_path):
        print(f"MAIL_FAIL: 日报文件不存在: {md_path}")
        sys.exit(1)

    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_code = os.environ.get("SMTP_AUTH_CODE", "").strip()
    mail_to = os.environ.get("MAIL_TO", "").strip() or smtp_user

    if not smtp_user or not smtp_code:
        print("MAIL_FAIL: 缺少环境变量 SMTP_USER 或 SMTP_AUTH_CODE")
        sys.exit(1)

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    date = extract_date(md_path, sys.argv[2] if len(sys.argv) > 2 else None)
    subject = f"AI 行业资讯速览 | {date}"
    html = build_email_html(md_text)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("AI 日报推送", "utf-8")), smtp_user))
    msg["To"] = formataddr((str(Header("老板", "utf-8")), mail_to))
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30) as server:
            server.login(smtp_user, smtp_code)
            server.sendmail(smtp_user, [mail_to], msg.as_string())
    except smtplib.SMTPAuthenticationError:
        print("MAIL_FAIL: SMTP 登录失败，请检查 SMTP_AUTH_CODE 是否为 16 位授权码（非 QQ 密码），且已开启 SMTP 服务")
        sys.exit(1)
    except Exception as e:
        print(f"MAIL_FAIL: {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"MAIL_SENT: {subject} -> {mail_to}")


if __name__ == "__main__":
    main()
