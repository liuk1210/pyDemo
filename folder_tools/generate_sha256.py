import hashlib
import os
import time
from pathlib import Path
from typing import Optional


def calculate_sha256(file_path: Path) -> Optional[str]:
    try:
        sha256 = hashlib.sha256()
        buffer_size = 1024 * 1024  # 1MB
        file_size = file_path.stat().st_size
        total_read = 0.0
        start_time = time.time() * 1000  # 毫秒
        last_update_time = start_time
        with open(file_path, 'rb', buffering=8192) as f:
            while True:
                buffer = f.read(buffer_size)
                if not buffer:
                    break
                sha256.update(buffer)
                current_time = time.time() * 1000
                total_read += len(buffer)
                if current_time - last_update_time >= 100.0 or total_read == file_size:
                    total_read_time = current_time - start_time
                    print_progress_info(total_read, file_size, total_read_time)
                    last_update_time = current_time
        return sha256.hexdigest()
    except Exception as e:
        print(f"未知错误: {file_path} - {str(e)}")
    return None


def print_progress_info(total_read: int, file_size: int, total_read_time: float):
    progress = total_read / file_size * 100
    progress_bar = get_progress_bar(progress)
    size_info = f"{format_size(total_read)}/{format_size(file_size)}"
    time_info = format_time(total_read_time)
    average_speed = total_read / (total_read_time / 1000) if total_read_time > 0 else 0
    speed_info = format_speed(average_speed)
    print(f"\r{progress_bar} {progress:.2f}% ({size_info}) [速度：{speed_info}，耗时：{time_info}]", end='', flush=True)


def get_progress_bar(progress: float) -> str:
    bar_length = 50
    filled_length = int(progress / 100 * bar_length)
    return "[" + "=" * filled_length + " " * (bar_length - filled_length) + "]"


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.2f} KB"
    elif size < 1024 ** 3:
        return f"{size / (1024 ** 2):.2f} MB"
    else:
        return f"{size / (1024 ** 3):.2f} GB"


def format_time(time_ms: float) -> str:
    if time_ms < 1000:
        return f"{int(time_ms)} ms"
    else:
        return f"{time_ms / 1000:.2f} s"


def format_speed(speed_bytes: float) -> str:
    if speed_bytes < 1024:
        return f"{speed_bytes:.2f} B/s"
    elif speed_bytes < 1024 ** 2:
        return f"{speed_bytes / 1024:.2f} KB/s"
    elif speed_bytes < 1024 ** 3:
        return f"{speed_bytes / (1024 ** 2):.2f} MB/s"
    else:
        return f"{speed_bytes / (1024 ** 3):.2f} GB/s"


def process_folder(folder_path: str):
    path = Path(folder_path)
    total_files = count_files(path)
    if total_files == 0:
        print("该文件夹下不存在文件！")
        return
    processed_files = 0
    create_count = 0
    exist_count = 0
    sha256_folder = path / 'sha256'
    for file_path in path.rglob('*'):
        if file_path.is_file() and not file_path.name.endswith('.sha256') and 'sha256' not in file_path.parent.parts:
            processed_files += 1
            print(f"正在处理第 {processed_files} 个文件，共 {total_files} 个，已创建 {create_count} 个sha256文件...")
            print(f"正在读取 {file_path.name} 并计算sha256中...")
            sha256 = calculate_sha256(file_path)
            if sha256 is None:
                continue
            print(f"\n文件：{file_path.name}")
            print(f"SHA256：{sha256}")
            try:
                file_size = file_path.stat().st_size
                sha256_filename = f"{file_path.name}.{sha256}.{file_size}.sha256"
                sha256_file = sha256_folder / sha256_filename
                created = create_file_with_directories(sha256_file)
                if created:
                    create_count += 1
                else:
                    exist_count += 1
                print()
            except Exception as e:
                print(f"未知错误: {file_path} - {str(e)}")
    print(f"总文件数：{total_files} ，已创建 {create_count} 个sha256文件，已存在 {exist_count} 个sha256文件")


def count_files(path: Path) -> int:
    return sum(1 for _ in path.rglob('*')
               if _.is_file()
               and not _.name.endswith('.sha256')
               and 'sha256' not in _.parent.parts)


def create_file_with_directories(file_path: Path) -> bool:
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
    if not file_path.exists():
        file_path.touch()
        print(f"文件已创建：{file_path}")
        return True
    else:
        print(f"文件已存在: {file_path}")
        return False


if __name__ == "__main__":
    user_input = input("请输入需要计算sha256值的根文件目录（默认为当前用户Downloads文件夹 ，直接回车使用默认值）：")
    if user_input.strip() == "":
        user_profile = os.environ.get('USERPROFILE')
        if user_profile:
            result = os.path.join(user_profile, 'Downloads')
            print(f"当前默认文件夹路径为：{result}\n")
        else:
            raise Exception("读取环境变量USERPROFILE失败，无法读取默认值，请输入文件目录")
    else:
        result = user_input
    process_folder(result)
