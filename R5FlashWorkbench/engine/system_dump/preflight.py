"""2A 固定读取清单及保守判定；本模块不访问 USB 或相机文件。"""

import hashlib


PREFLIGHT_FILES = {
    "version.bin": "/version.txt",
    "fstab.txt": "/sbin/initrc/fstab",
    "fstab-ext.txt": "/sbin/initrc/fstab.ext",
    "mediainfo.txt": "/tmp/jiritsu/mediainfo.txt",
    "etc-preload.bin": "/etc/ld.so.preload",
    "tmp-preload.bin": "/tmp/ld.so.preload",
}
BASELINE_VERSION_SHA256 = "34c44c5d2974d822eb8c43953317c8ccecaa51b72ffad8693d1cd3261a4fa79b"


def wire_path(path: str) -> bytes:
    """Work 内路径直接使用，其余路径按已经核对的穿越形式编码。"""
    return (path if path.startswith("/tmp/jiritsu/") else "/tmp/jiritsu/../.." + path).encode("ascii")


def assess_preload(contents: dict[str, bytes]) -> dict:
    """只分类取得的内容；无法读取的路径始终未知。"""
    preload = {}
    for label, path in (("etc", "/etc/ld.so.preload"), ("tmp", "/tmp/ld.so.preload")):
        if path not in contents:
            state = "unknown"
        elif not contents[path]:
            state = "readable_empty"
        elif not contents[path].strip(b" \t\r\n\v\f"):
            state = "readable_whitespace"
        else:
            state = "readable_non_whitespace_requires_review"
        preload[label] = {"path": path, "state": state, "absence_proven": False}
    etc, tmp = "/etc/ld.so.preload", "/tmp/ld.so.preload"
    comparison = "unknown"
    if etc in contents and tmp in contents:
        comparison = "same" if contents[etc] == contents[tmp] else "different"
    return {"preload": preload, "preload_path_content_comparison": comparison}


def assess_preflight(files: list[dict], contents: dict[str, bytes]) -> dict:
    """只判定读取结果；不从错误码、空文件或内容相同推断部署安全。"""
    paths = tuple(PREFLIGHT_FILES.values())
    complete = (tuple(record["path"] for record in files) == paths
                and all(record["status"] in ("read", "empty", "service_error") for record in files))
    version = contents.get("/version.txt")
    return {
        "collection_complete": complete,
        "all_files_read": complete and all(record["status"] in ("read", "empty") for record in files),
        "baseline_version_sha256": BASELINE_VERSION_SHA256,
        "version_matches_stage1": None if version is None else hashlib.sha256(version).hexdigest() == BASELINE_VERSION_SHA256,
        **assess_preload(contents),
        "runtime_mapping_verified": False,
        "deployment_allowed": False,
        "review_required": True,
        "notes": [
            "0x10000006 等文件错误只记未知，不能证明不存在或可写",
            "启动配置与 mediainfo 缓存不能独立证明运行时挂载源",
            "空白或两路径内容相同不证明文件类型、链接、权限或别名关系",
            "完成收集不授权上传、预加载、DEBUG 或格式化，必须人工审查",
        ],
    }
