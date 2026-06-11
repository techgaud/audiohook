#!/usr/bin/env python3
"""Assemble rendered audio into a chaptered M4B.

Two steps:
  1. concat per-chunk WAVs into one WAV per chapter (stdlib wave, all chunks share
     Kokoro's sample format, so raw frame concatenation is correct and lossless).
  2. encode the chapter WAVs into a single M4B (AAC) with chapter markers, title,
     author, and an optional cover, via one ffmpeg call using an FFMETADATA file.

Only the final encode needs ffmpeg (brew install ffmpeg). Everything else is stdlib
and testable anywhere.
"""
import contextlib
import os
import subprocess
import wave


def concat_wavs(wav_paths, out_path):
    params = None
    with wave.open(out_path, "wb") as out:
        for p in wav_paths:
            with wave.open(p, "rb") as w:
                if params is None:
                    params = w.getparams()
                    out.setparams(params)
                out.writeframes(w.readframes(w.getnframes()))
    return out_path


def wav_duration(path):
    with contextlib.closing(wave.open(path, "rb")) as w:
        return w.getnframes() / float(w.getframerate())


def _esc(v):
    # FFMETADATA requires =, ;, #, \ and newlines to be backslash-escaped
    return str(v).replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", "\\\n")


def build_ffmetadata(chapter_titles, durations, title, author):
    out = [";FFMETADATA1", f"title={_esc(title)}", f"artist={_esc(author)}",
           f"album={_esc(title)}", f"genre=Audiobook"]
    t_ms = 0
    for ch_title, dur in zip(chapter_titles, durations):
        start = t_ms
        t_ms += int(round(dur * 1000))
        out += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={start}",
                f"END={t_ms}", f"title={_esc(ch_title)}"]
    return "\n".join(out) + "\n"


def to_m4b(chapter_wavs, chapter_titles, out_m4b, *, title, author,
           cover=None, bitrate="64k", workdir="."):
    """Combine chapter WAVs into out_m4b with chapter markers and metadata."""
    durations = [wav_duration(w) for w in chapter_wavs]

    concat_list = os.path.join(workdir, "_concat.txt")
    with open(concat_list, "w") as f:
        for w in chapter_wavs:
            f.write(f"file '{os.path.abspath(w)}'\n")

    meta_path = os.path.join(workdir, "_ffmeta.txt")
    with open(meta_path, "w") as f:
        f.write(build_ffmetadata(chapter_titles, durations, title, author))

    cmd = ["ffmpeg", "-y",
           "-f", "concat", "-safe", "0", "-i", concat_list,
           "-i", meta_path]
    maps = ["-map", "0:a"]
    if cover and os.path.exists(cover):
        cmd += ["-i", cover]
        maps += ["-map", "2:v"]
    cmd += maps + ["-map_metadata", "1",
                   "-c:a", "aac", "-b:a", bitrate]
    if cover and os.path.exists(cover):
        cmd += ["-c:v", "copy", "-disposition:v:0", "attached_pic"]
    cmd += ["-movflags", "+faststart", out_m4b]

    subprocess.run(cmd, check=True)
    os.remove(concat_list)
    os.remove(meta_path)
    return out_m4b


if __name__ == "__main__":
    # Self-test the stdlib parts (no ffmpeg): synthesize silent WAVs, concat, and
    # verify the FFMETADATA chapter timestamps line up with the durations.
    import struct
    import tempfile

    def make_wav(path, seconds, rate=24000):
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(struct.pack("<" + "h" * int(rate * seconds), *([0] * int(rate * seconds))))

    d = tempfile.mkdtemp()
    chunks = [os.path.join(d, f"c{i}.wav") for i in range(3)]
    for i, c in enumerate(chunks):
        make_wav(c, 0.5 + i * 0.5)               # 0.5s, 1.0s, 1.5s
    ch = concat_wavs(chunks, os.path.join(d, "chapter0.wav"))
    print("chapter duration:", round(wav_duration(ch), 3), "s (expected 3.0)")

    meta = build_ffmetadata(["I", "II"], [3.0, 2.0], "The Time Machine", "H. G. Wells")
    print("\n--- FFMETADATA ---")
    print(meta)
    assert "START=0" in meta and "END=3000" in meta and "START=3000" in meta and "END=5000" in meta
    print("chapter timestamps OK")
