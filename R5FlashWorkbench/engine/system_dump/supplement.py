"""五路径最小补证的固定清单及保守判定；不导入设备模块。"""

import hashlib

from .preflight import BASELINE_VERSION_SHA256, assess_preload


SUPPLEMENT_FILES = {
    "version.bin": "/version.txt",
    "etc-parent-version.bin": "/etc/../version.txt",
    "tmp-parent-version.bin": "/tmp/../version.txt",
    "etc-preload.bin": "/etc/ld.so.preload",
    "tmp-preload.bin": "/tmp/ld.so.preload",
}
CONTROL_PATHS = tuple(SUPPLEMENT_FILES.values())[:3]


def control_matches(content: bytes | None) -> bool:
    """三个对照都必须匹配历史十九字节，不能仅相互匹配。"""
    return (content is not None and len(content) == 19
            and hashlib.sha256(content).hexdigest() == BASELINE_VERSION_SHA256)


def assess_supplement(files: list[dict], contents: dict[str, bytes]) -> dict:
    """成功只说明当时可读；错误不证明不存在，对照不证明挂载源。"""
    complete = (tuple(r["path"] for r in files) == tuple(SUPPLEMENT_FILES.values())
                and all(r["status"] in ("read", "empty", "service_error") for r in files))
    controls = [{"path": path, "matches_baseline": control_matches(contents[path]) if path in contents else None}
                for path in CONTROL_PATHS]
    return {
        "collection_complete": complete,
        "all_files_read": complete and all(r["status"] in ("read", "empty") for r in files),
        "baseline_version_sha256": BASELINE_VERSION_SHA256,
        "controls": controls,
        "controls_match_baseline": all(c["matches_baseline"] is True for c in controls),
        **assess_preload(contents),
        "runtime_mapping_verified": False,
        "deployment_allowed": False,
        "review_required": True,
        "notes": [
            "对照路径保留 ..，成功只支持当时路径可解析，不证明实际挂载源或链接关系",
            "0x10000006 等文件错误只记未知，不能证明不存在或可写",
            "空白或两路径内容相同不证明文件类型、链接或部署安全",
            "主机接收上限不能限制固件按 stat 长度分配或读取文件",
            "本次只收证，不授权上传、预加载、DEBUG 或格式化",
        ],
    }
