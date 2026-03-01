from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansMonoCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def _display_width(text: str) -> int:
    width = 0
    for ch in text:
        code = ord(ch)
        if code <= 0x1F or 0x7F <= code <= 0x9F:
            continue
        if code >= 0x2E80:
            width += 2
        else:
            width += 1
    return width


def _slice_by_display_width(text: str, max_width: int) -> tuple[str, str]:
    width = 0
    idx = 0
    for idx, ch in enumerate(text):
        ch_width = 2 if ord(ch) >= 0x2E80 else 1
        if width + ch_width > max_width:
            return text[:idx], text[idx:]
        width += ch_width
    return text, ""


def _wrap_line(line: str, max_chars: int) -> list[str]:
    if not line:
        return [""]
    chunks: list[str] = []
    remaining = line
    while _display_width(remaining) > max_chars:
        left, right = _slice_by_display_width(remaining, max_chars)
        chunks.append(left)
        remaining = right
    chunks.append(remaining)
    return chunks


def _compress_output_lines(lines: list[str], max_output_lines: int) -> list[str]:
    if max_output_lines <= 0 or len(lines) <= max_output_lines:
        return lines
    head = max(3, max_output_lines // 3)
    tail = max(3, max_output_lines - head - 1)
    return [*lines[:head], f"... ({len(lines) - head - tail} lines omitted) ...", *lines[-tail:]]


def _run_shell_command(
    command: str,
    cwd: Path,
    timeout: int,
    *,
    force_english: bool,
    max_output_lines: int,
    fail_on_error: bool,
) -> list[str]:
    env = os.environ.copy()
    if force_english:
        env["LANGUAGE_AUTO"] = "false"
        env["LC_ALL"] = "C.UTF-8"
        env["LANG"] = "C.UTF-8"
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    lines: list[str] = []
    if proc.stdout:
        lines.extend(_strip_ansi(proc.stdout).splitlines())
    if proc.stderr:
        lines.extend(_strip_ansi(proc.stderr).splitlines())
    if proc.returncode != 0:
        if fail_on_error:
            message = "\n".join(lines[-20:]) if lines else "(no output)"
            raise RuntimeError(f"Command failed (exit {proc.returncode}): {command}\n{message}")
        lines.append(f"[exit {proc.returncode}]")
    if not lines:
        lines = ["(no output)"]
    return _compress_output_lines(lines, max_output_lines=max_output_lines)


def _draw_terminal_frame(
    lines: list[str],
    *,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    line_height: int,
) -> Image.Image:
    img = Image.new("RGB", (width, height), "#0b1220")
    draw = ImageDraw.Draw(img)

    # Top terminal bar
    draw.rectangle((0, 0, width, 52), fill="#111827")
    draw.ellipse((18, 18, 30, 30), fill="#ef4444")
    draw.ellipse((38, 18, 50, 30), fill="#f59e0b")
    draw.ellipse((58, 18, 70, 30), fill="#10b981")
    draw.text((88, 16), "pandapower-agent demo terminal", fill="#e5e7eb", font=font)

    left_padding = 20
    top_padding = 62
    bottom_padding = 12
    max_rows = max(1, (height - top_padding - bottom_padding) // line_height)
    visible_lines = lines[-max_rows:]

    y = top_padding
    for line in visible_lines:
        color = "#d1d5db"
        if line.startswith("$ "):
            color = "#22c55e"
        elif line.startswith("assistant>"):
            color = "#60a5fa"
        elif line.startswith("[exit"):
            color = "#fca5a5"
        draw.text((left_padding, y), line, fill=color, font=font)
        y += line_height
    return img


def generate_terminal_demo(
    *,
    commands: list[str],
    cwd: Path,
    output: Path,
    fps: int,
    width: int,
    height: int,
    font_size: int,
    typing_step: int,
    hold_frames: int,
    reveal_chunk_lines: int,
    max_output_lines: int,
    force_english: bool,
    fail_on_error: bool,
    timeout: int,
    font_path: Path | None,
) -> None:
    if font_path is not None:
        font = ImageFont.truetype(str(font_path), size=font_size)
    else:
        font = _load_font(font_size)
    line_height = int(font_size * 1.45)
    # Mono-oriented approximation.
    char_width = max(7, int(font_size * 0.62))
    max_chars = max(30, (width - 40) // char_width)

    frames: list[Image.Image] = []
    buffer_lines: list[str] = []

    for command in commands:
        typed_prefix = "$ "
        for i in range(0, len(command) + 1, max(1, typing_step)):
            preview = typed_prefix + command[:i]
            preview_wrapped: list[str] = []
            for part in _wrap_line(preview, max_chars):
                preview_wrapped.append(part)
            frame = _draw_terminal_frame(
                buffer_lines + preview_wrapped,
                width=width,
                height=height,
                font=font,
                line_height=line_height,
            )
            frames.append(frame)

        final_command_lines = _wrap_line(typed_prefix + command, max_chars)
        buffer_lines.extend(final_command_lines)
        frames.append(
            _draw_terminal_frame(
                buffer_lines,
                width=width,
                height=height,
                font=font,
                line_height=line_height,
            )
        )

        output_lines = _run_shell_command(
            command,
            cwd=cwd,
            timeout=timeout,
            force_english=force_english,
            max_output_lines=max_output_lines,
            fail_on_error=fail_on_error,
        )
        wrapped_lines: list[str] = []
        for line in output_lines:
            wrapped_lines.extend(_wrap_line(line, max_chars))
        chunk = max(1, reveal_chunk_lines)
        for idx in range(0, len(wrapped_lines), chunk):
            buffer_lines.extend(wrapped_lines[idx : idx + chunk])
            frames.append(
                _draw_terminal_frame(
                    buffer_lines,
                    width=width,
                    height=height,
                    font=font,
                    line_height=line_height,
                )
            )

        for _ in range(max(1, hold_frames)):
            frames.append(
                _draw_terminal_frame(
                    buffer_lines,
                    width=width,
                    height=height,
                    font=font,
                    line_height=line_height,
                )
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    frame_duration_ms = int(1000 / max(1, fps))
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=frame_duration_ms,
        loop=0,
        optimize=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate terminal-style demo GIF with typed commands and outputs.")
    parser.add_argument("--output", type=Path, default=Path("docs/assets/quick-demo.gif"))
    parser.add_argument("--cwd", type=Path, default=Path("."))
    parser.add_argument("--fps", type=int, default=7)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--font-size", type=int, default=22)
    parser.add_argument("--typing-step", type=int, default=3)
    parser.add_argument("--hold-frames", type=int, default=8)
    parser.add_argument("--reveal-chunk-lines", type=int, default=2, help="How many output lines to reveal per frame.")
    parser.add_argument("--max-output-lines", type=int, default=36, help="Limit output lines shown for each command.")
    parser.add_argument(
        "--font-path", type=Path, default=None, help="Optional custom font path (use a CJK font for Chinese)."
    )
    parser.add_argument(
        "--force-english",
        action="store_true",
        help="Set LANGUAGE_AUTO=false and C.UTF-8 locale for child commands to reduce mixed-language output.",
    )
    parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="Do not abort GIF generation when a command exits non-zero.",
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--preset",
        choices=["quick", "showcase"],
        default="showcase",
        help="Built-in command set for the demo.",
    )
    parser.add_argument("--command", action="append", default=None, help="Command to run; can be set multiple times.")
    args = parser.parse_args()

    quick_commands = [
        "agent networks --max 5",
        "agent use case14",
        'agent run "run AC power flow and summarize voltage and loading risks in 4 concise English bullets"',
    ]
    showcase_commands = [
        "agent networks --max 8",
        "agent doctor --format table",
        "printf '/use case14\\nrun AC power flow and summarize voltage and loading risks in concise English bullets\\nsave current scenario as demo_case\\n/scenarios\\nexit\\n' | STARTUP_SHOW_NETWORKS=false agent chat",
        "agent export --type summary --path ./outputs/summary.json",
        "agent plot-network --path ./outputs/network_plot.png",
    ]
    commands = args.command or (showcase_commands if args.preset == "showcase" else quick_commands)

    generate_terminal_demo(
        commands=commands,
        cwd=args.cwd,
        output=args.output,
        fps=args.fps,
        width=args.width,
        height=args.height,
        font_size=args.font_size,
        typing_step=args.typing_step,
        hold_frames=args.hold_frames,
        reveal_chunk_lines=args.reveal_chunk_lines,
        max_output_lines=args.max_output_lines,
        force_english=args.force_english,
        fail_on_error=not args.allow_errors,
        timeout=args.timeout,
        font_path=args.font_path,
    )
    print(f"Wrote GIF to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
