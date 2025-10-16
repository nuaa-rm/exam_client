"""verify_signatures.py

用法:
    python -m utils.verify_signatures

功能:
1. 扫描 media 下每个 recorder 文件夹(按项目中实现为: media/<recorder_name>)，检查每 6 个 ts 文件至少有 1 个对应的 .sig 文件；如果缺失，输出 warning 并给出缺失文件编号范围和时间范围。
2. 检查所有 .sig 文件中的 sid 字段是否一致，如果不一致输出 warning 列表。
3. 对有签名的文件校验签名是否正确，如果不正确输出具体文件名。

"""
import sys
from pathlib import Path
import hashlib
import re
import datetime
from typing import List, Tuple, Optional

ROOT = Path(__file__).resolve().parents[1]
MEDIA_DIR = ROOT / 'media'

SIG_PATTERN = re.compile(r'^(?P<hash>[0-9a-fA-F]{40})\+(?P<sid>.*)$')


def load_sig(sig_path: Path) -> Optional[Tuple[str, str]]:
    try:
        text = sig_path.read_text(encoding='utf-8').strip()
    except Exception:
        return None
    m = SIG_PATTERN.match(text)
    if not m:
        return None
    return m.group('hash'), m.group('sid')


def compute_hash_for_file(ts_path: Path, sid: str) -> str:
    salt = f"CkyfExamClient_video_signature_{sid}"
    h = hashlib.sha1()
    h.update(salt.encode('utf-8'))
    # read in chunks
    with open(ts_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def scan_recorder_folder(folder: Path) -> Tuple[List[str], List[str], List[str]]:
    """
    Scan one recorder folder.
    Returns: (warnings, sid_list, bad_signatures)
    warnings: list of warning messages about missing signatures
    sid_list: list of sids found in .sig files (may contain duplicates)
    bad_signatures: list of filenames where signature mismatch
    """
    warnings: List[str] = []
    sid_list: List[str] = []
    bad_signatures: List[str] = []

    if not folder.exists() or not folder.is_dir():
        return warnings, sid_list, bad_signatures

    # collect ts files and sig files
    ts_files = sorted(folder.glob('video_*.ts'), key=lambda p: int(p.stem.split('_')[1]) if '_' in p.stem else -1)
    sig_files = {p.stem: p for p in folder.glob('video_*.sig')}

    # 连续扫描：连续 N 个（这里 N=6）没有签名则记录一个缺失区间，遇到签名则重置计数
    missing_ranges: List[Tuple[int, int, datetime.datetime, datetime.datetime]] = []
    if ts_files:
        N = 6
        consec = 0
        range_start_idx = None
        range_start_time = None

        for ts in ts_files:
            idx = int(ts.stem.split('_')[1])
            sig_name = ts.with_suffix('.sig').stem
            has_sig = sig_name in sig_files

            if not has_sig:
                # 未签名
                consec += 1
                if consec == 1:
                    # 记录潜在区间开始
                    range_start_idx = idx
                    range_start_time = datetime.datetime.fromtimestamp(ts.stat().st_mtime)

                # 如果达到了 N，则记录/开启缺失区间
                if consec >= N:
                    # 结束索引为当前 idx
                    end_idx = idx
                    end_time = datetime.datetime.fromtimestamp(ts.stat().st_mtime)
                    # 确保 start 不为 None（兜底使用当前 idx/time）
                    s_idx = range_start_idx if range_start_idx is not None else idx
                    s_time = range_start_time if range_start_time is not None else datetime.datetime.fromtimestamp(ts.stat().st_mtime)
                    # 如果上一个记录与当前相邻或重叠，会在后面合并
                    missing_ranges.append((s_idx, end_idx, s_time, end_time))
                    # 注意：不要在这里重置 range_start，因为如果后续继续未签名我们希望扩展上次记录；
                    # 但是为了避免重复记录重叠范围，我们将移动 range_start 到下一个未签名的开始
                    # 将 consec 继续累积以继续检测扩展
            else:
                # 有签名，重置连续计数（结束当前潜在区间）
                consec = 0
                range_start_idx = None
                range_start_time = None

        # 合并可能重叠或相邻的 missing_ranges
        if missing_ranges:
            missing_ranges.sort(key=lambda t: t[0])
            merged: List[Tuple[int, int, datetime.datetime, datetime.datetime]] = []
            for start_idx, end_idx, start_time, end_time in missing_ranges:
                if not merged:
                    merged.append((start_idx, end_idx, start_time, end_time))
                    continue
                last_start, last_end, last_st, last_et = merged[-1]
                # 如果当前范围与上一个范围相邻或重叠，合并
                if start_idx <= last_end + 1:
                    new_end = max(last_end, end_idx)
                    new_et = max(last_et, end_time)
                    merged[-1] = (last_start, new_end, last_st, new_et)
                else:
                    merged.append((start_idx, end_idx, start_time, end_time))

            for start_idx, end_idx, start_time, end_time in merged:
                warnings.append(
                    f"签名缺失: {folder.name} 文件编号范围 {start_idx}-{end_idx}, 时间范围 {start_time} - {end_time}"
                )

    # gather sids and validate signatures
    for sig_path in folder.glob('video_*.sig'):
        sig_info = load_sig(sig_path)
        if not sig_info:
            warnings.append(f"无法解析签名文件: {sig_path.name}")
            continue
        hash_value, sid = sig_info
        sid_list.append(sid)

        ts_candidate = folder / (sig_path.stem + '.ts')
        if not ts_candidate.exists():
            warnings.append(f"签名文件但对应 ts 不存在: {sig_path.name}")
            continue

        # compute and compare
        try:
            computed = compute_hash_for_file(ts_candidate, sid)
        except Exception as e:
            warnings.append(f"计算文件哈希失败: {ts_candidate.name}, 错误: {e}")
            continue
        if computed.lower() != hash_value.lower():
            bad_signatures.append(ts_candidate.name)

    return warnings, sid_list, bad_signatures


def main() -> int:
    if not MEDIA_DIR.exists():
        print(f"media 目录不存在: {MEDIA_DIR}")
        return 1

    overall_warnings: List[str] = []
    overall_sids: List[str] = []
    overall_bad: List[str] = []

    for folder in sorted(MEDIA_DIR.iterdir()):
        if not folder.is_dir():
            continue
        warnings, sids, bad = scan_recorder_folder(folder)
        if warnings:
            for w in warnings:
                print("WARNING:", w)
        overall_warnings.extend(warnings)
        overall_sids.extend(sids)
        overall_bad.extend([f"{folder.name}/{b}" for b in bad])

    # check sids consistency
    unique_sids = sorted(set(overall_sids))
    if len(unique_sids) > 1:
        print("WARNING: 不一致的 sid 列表:", unique_sids)

    # report bad signatures
    if overall_bad:
        print("错误签名文件: ")
        for b in overall_bad:
            print(" -", b)

    print("校验完成。")
    return 0


if __name__ == '__main__':
    sys.exit(main())
