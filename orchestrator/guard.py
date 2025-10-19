import fnmatch
import os
import pathlib

def ensure_guarded_write(guard_patterns: list[str], root: str, write_path: str):
    """
    Kiểm tra xem đường dẫn ghi file có hợp lệ so với các mẫu guard_patterns không.
    Nếu không hợp lệ, sẽ raise PermissionError.
    """
    # Đảm bảo các đường dẫn là tuyệt đối và chuẩn hóa
    abs_root = pathlib.Path(root).resolve()
    abs_target = abs_root.joinpath(write_path).resolve()

    # Lấy đường dẫn tương đối của file đích so với thư mục gốc
    try:
        rel_path = abs_target.relative_to(abs_root)
    except ValueError:
        # File đích nằm ngoài thư mục gốc của dự án
        raise PermissionError(f"Write blocked: Path {abs_target} is outside of project root {abs_root}")

    # Kiểm tra xem đường dẫn tương đối có khớp với bất kỳ mẫu nào không
    # Dùng as_posix() để đảm bảo dấu / trên mọi HĐH
    allowed = any(fnmatch.fnmatch(rel_path.as_posix(), pat) for pat in guard_patterns)
    
    if not allowed:
        raise PermissionError(f"Write blocked by guard paths: '{rel_path}' not in {guard_patterns}")
    
    print(f"[Guard] ✅ Write allowed for path: {rel_path}")
    return abs_target
